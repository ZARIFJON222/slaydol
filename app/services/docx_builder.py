from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor


def _style_run(run, size_pt: int = 14, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.name = "Times New Roman"
    run.font.size = Pt(size_pt)
    run.bold = bold
    if color:
        run.font.color.rgb = color


def _add_body_para(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Cm(1.25)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    _style_run(r, size_pt=14)


def _add_section_heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    _style_run(r, size_pt=15, bold=True, color=RGBColor(20, 35, 65))


def build_referat_docx(
    data: dict[str, Any],
    doc_type: str,
    author: str,
    lang: str,
    out_path: Path,
) -> Path:
    doc = Document()

    # GOST A4 Margins: Left 3.0 cm, Right 1.5 cm, Top/Bottom 2.0 cm
    for sec in doc.sections:
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        sec.left_margin = Cm(3.0)
        sec.right_margin = Cm(1.5)
        sec.top_margin = Cm(2.0)
        sec.bottom_margin = Cm(2.0)

    # --- 1. TITUL VARAG'I (COVER PAGE) ---
    top_label = (
        "O'ZBEKISTON RESPUBLIKASI OLIY TA'LIM, FAN VA INNOVATSIYALAR VAZIRLIGI"
        if lang == "uz"
        else "МИНИСТЕРСТВО ВЫСШЕГО ОБРАЗОВАНИЯ, НАУКИ И ИННОВАЦИЙ"
    )
    p_top = doc.add_paragraph()
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top.paragraph_format.space_after = Pt(24)
    _style_run(p_top.add_run(top_label), size_pt=12, bold=True)

    subj = str(data.get("subject_area", ""))
    if subj:
        p_subj = doc.add_paragraph()
        p_subj.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_subj.paragraph_format.space_after = Pt(60)
        lbl_fan = f"Fan: {subj}" if lang == "uz" else f"Дисциплина: {subj}"
        _style_run(p_subj.add_run(lbl_fan), size_pt=13)

    p_type = doc.add_paragraph()
    p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_type.paragraph_format.space_before = Pt(36)
    p_type.paragraph_format.space_after = Pt(14)
    _style_run(p_type.add_run(doc_type.upper()), size_pt=24, bold=True, color=RGBColor(20, 35, 65))

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(70)
    mavzu_lbl = "Mavzu: " if lang == "uz" else "Тема: "
    _style_run(p_title.add_run(mavzu_lbl + str(data.get("title", ""))), size_pt=16, bold=True)

    if author:
        p_auth = doc.add_paragraph()
        p_auth.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_auth.paragraph_format.space_after = Pt(80)
        by_lbl = "Bajardi: " if lang == "uz" else "Выполнил(а): "
        _style_run(p_auth.add_run(f"{by_lbl}{author}"), size_pt=14, bold=True)

    p_year = doc.add_paragraph()
    p_year.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_year.paragraph_format.space_before = Pt(40)
    _style_run(p_year.add_run(f"{datetime.now().year}"), size_pt=14, bold=True)

    doc.add_page_break()

    # --- 2. REJA / MUNDARIJA ---
    toc_title = "REJA:" if lang == "uz" else "СОДЕРЖАНИЕ:"
    _add_section_heading(doc, toc_title)
    intro_lbl = "Kirish" if lang == "uz" else "Введение"
    concl_lbl = "Xulosa" if lang == "uz" else "Заключение"
    refs_lbl = "Foydalanilgan adabiyotlar" if lang == "uz" else "Список литературы"

    sections = data.get("sections") or []
    toc_items = [intro_lbl] + [
        f"{i}. {sec.get('heading', '')}" for i, sec in enumerate(sections, start=1)
    ] + [concl_lbl, refs_lbl]

    for item in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.line_spacing = 1.35
        p.paragraph_format.space_after = Pt(4)
        _style_run(p.add_run(item), size_pt=14)

    # --- 3. KIRISH ---
    _add_section_heading(doc, intro_lbl.upper())
    for para in data.get("intro") or []:
        _add_body_para(doc, str(para))

    # --- 4. ASOSIY QISM ---
    for i, sec in enumerate(sections, start=1):
        _add_section_heading(doc, f"{i}. {sec.get('heading', '')}")
        for para in sec.get("paragraphs") or []:
            _add_body_para(doc, str(para))

    # --- 5. XULOSA ---
    _add_section_heading(doc, concl_lbl.upper())
    for para in data.get("conclusion") or []:
        _add_body_para(doc, str(para))

    # --- 6. ADABIYOTLAR ---
    _add_section_heading(doc, refs_lbl.upper())
    for idx, ref in enumerate(data.get("references") or [], start=1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.line_spacing = 1.35
        p.paragraph_format.space_after = Pt(4)
        _style_run(p.add_run(f"{idx}. {ref}"), size_pt=13)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
