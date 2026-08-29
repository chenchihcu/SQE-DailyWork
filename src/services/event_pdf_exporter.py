from __future__ import annotations

import base64
import logging
from datetime import datetime
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont, QImage, QTextDocument

from services import attachment_manager
from services.pdf_html_helpers import (
    _RawHtml,
    sanitize_filename_part,
    _write_html_pdf,
    _preferred_pdf_font_family,
    _html_document,
    _brief_html_document,
    _summary_panel,
    _section,
    _wide_row,
    _text_section,
    _cell,
    _plain_cell,
    _positive_number_or_dash,
    _attachment_display_size,
    _BORDER,
    _TEXT_PRIMARY,
    _TEXT_SECONDARY,
)


def _event_type(row: dict) -> str:
    event_type = str(row.get("event_type") or "").strip().upper()
    if event_type not in {"VISIT", "ANOMALY"}:
        raise ValueError("Event type is required")
    return event_type


def default_event_pdf_filename(
    row: dict,
    detail: dict,
) -> str:
    event_type = _event_type(row)
    supplier = sanitize_filename_part(detail.get("supplier_name") or row.get("supplier_name"))
    if event_type == "VISIT":
        visit_date = str(detail.get("visit_date") or row.get("event_date") or "").replace("-", "")
        visit_date = sanitize_filename_part(visit_date, fallback="未填日期")
        return f"SQE_訪廠紀錄_{visit_date}_{supplier}.pdf"

    ref_no = sanitize_filename_part(
        detail.get("anomaly_no") or row.get("ref_no") or row.get("event_id"),
        fallback="未編號",
    )
    return f"SQE_異常單_{ref_no}_{supplier}.pdf"


def _event_report_context(
    row: dict, detail: dict, exported_at: datetime | None
) -> tuple[str, str, str, object]:
    """Resolve the (event_type, issued_at_text, reference_no, status_value)
    preamble shared by the full and brief report builders, which previously
    each re-derived it inline (audit finding D16)."""
    event_type = _event_type(row)
    issued_at = exported_at or datetime.now()
    return (
        event_type,
        issued_at.strftime("%Y-%m-%d %H:%M:%S"),
        _report_reference(row, detail, event_type),
        detail.get("status") or row.get("status"),
    )


def _closing_info_section(
    detail: dict, status_value: object, fields: list[tuple[str, object]]
) -> str | None:
    """Return the 結案資訊 section when the anomaly is closed (or carries an
    improvement note); each builder supplies its own field list."""
    if str(status_value or "").strip() == "已結案" or detail.get("improvement_desc"):
        return _section("結案資訊", fields)
    return None


def _assemble_report_body(issued_at_text: str, sections: list[str]) -> str:
    return "".join(
        [
            _summary_panel([("列印時間", issued_at_text, "text")]),
            *sections,
        ]
    )


def build_event_pdf_html(
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
    exported_at: datetime | None = None,
) -> str:
    event_type, issued_at_text, reference_no, status_value = _event_report_context(
        row, detail, exported_at
    )

    if event_type == "VISIT":
        title = "供應商訪廠紀錄報告"
        meta_lines = [
            ("訪廠日期", _plain_cell(detail.get("visit_date") or row.get("event_date"))),
        ]
        sections = [
            _section(
                "基本資料",
                [
                    ("日期", detail.get("visit_date")),
                    ("供應商", detail.get("supplier_name")),
                    ("品名", detail.get("product_name")),
                    ("階段", detail.get("product_stage")),
                    ("工單", detail.get("work_order_no")),
                    ("數量", _positive_number_or_dash(detail.get("production_qty"))),
                ],
                status_value=status_value,
            ),
            _text_section("摘要", detail.get("summary")),
        ]
        defect_note_section = _visit_defect_notes_section(detail)
        if defect_note_section:
            sections.append(defect_note_section)
    else:
        linked_visit_id = str(
            row.get("linked_visit_id") or detail.get("visit_id") or ""
        ).strip()
        title = "訪廠異常追蹤報告" if linked_visit_id else "供應商異常處理報告"
        meta_lines = [
            ("異常案號", _plain_cell(reference_no)),
        ]

        anomaly_fields: list[tuple[str, object]] = [
            ("日期", detail.get("anomaly_date") or row.get("event_date")),
            ("異常來源", detail.get("anomaly_source")),
            ("供應商", detail.get("supplier_name")),
            ("品名", detail.get("product_name")),
            ("階段", detail.get("product_stage")),
            ("原物料進貨單號", detail.get("material_receipt_no")),
            ("廠內製令單號", detail.get("internal_work_order_no")),
            ("委外製令單號", detail.get("outsource_work_order") or row.get("work_order_no")),
            ("委外進貨單號", detail.get("outsource_receipt_no")),
            ("數量", _positive_number_or_dash(detail.get("batch_qty"))),
            ("分類", detail.get("category")),
            ("批號", detail.get("product_lot_no")),
            ("責任人", detail.get("responsible_person")),
            ("預計回覆日", detail.get("due_date")),
        ]

        extra_rows: list[str] = []
        if linked_visit_id:
            extra_rows.append(
                _wide_row("關聯訪廠", _linked_visit_inline(row, linked_visit))
            )

        sections = [
            _section(
                "基本資料",
                anomaly_fields,
                extra_rows=extra_rows,
            ),
        ]
        sections.append(
            _text_section("問題描述", detail.get("problem_desc") or row.get("content"))
        )
        if str(detail.get("pending_items") or "").strip():
            sections.append(
                _text_section("確認事項", detail.get("pending_items"))
            )

        anomaly_id = str(detail.get("id") or row.get("event_id") or "").strip()
        if anomaly_id:
            try:
                from services.appearance_preferences_service import load_application_preferences

                prefs = load_application_preferences()
                include_hypothesis_png = bool(
                    getattr(prefs, "export_include_charts", True)
                )
            except Exception:
                include_hypothesis_png = True
            overview, open_actions, hypotheses = _anomaly_export_enrichment(anomaly_id)
            sections.append(_quality_overview_section(overview, open_actions))
            hypothesis_html = _hypothesis_tree_section(
                hypotheses,
                include_png=include_hypothesis_png,
            )
            if hypothesis_html:
                sections.append(hypothesis_html)

        closing_section = _closing_info_section(
            detail,
            status_value,
            [
                ("結案日", detail.get("closed_at")),
                ("改善說明", detail.get("improvement_desc")),
            ],
        )
        if closing_section:
            sections.append(closing_section)
        attachment_html = _anomaly_attachment_block(
            detail.get("id") or row.get("id")
        )
        if attachment_html:
            sections.append(attachment_html)

    body = _assemble_report_body(issued_at_text, sections)
    return _html_document(title, body, _preferred_pdf_font_family(), meta_lines)


def _export_html_pdf(
    path: str | Path,
    build_html,
    *,
    success_prefix: str,
    failure_log: str,
    failure_prefix: str,
    missing_msg: str,
) -> tuple[bool, str]:
    """Shared normalize-suffix → mkdir → render → write → verify pipeline for
    the full and brief PDF exports, which previously copy-pasted it with only
    the HTML builder and message texts differing (audit finding D17)."""
    try:
        output = Path(path)
        if output.suffix.lower() != ".pdf":
            output = output.with_suffix(".pdf")
        output.parent.mkdir(parents=True, exist_ok=True)

        html = build_html()
        _write_html_pdf(html, output)
        if not output.exists() or output.stat().st_size <= 0:
            raise RuntimeError(missing_msg)
        return True, f"{success_prefix}{output}"
    except Exception as exc:
        logger.exception(failure_log)
        return False, f"{failure_prefix}{exc}"


def export_event_pdf(
    path: str | Path,
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
) -> tuple[bool, str]:
    return _export_html_pdf(
        path,
        lambda: build_event_pdf_html(row, detail, linked_visit=linked_visit),
        success_prefix="已匯出至：",
        failure_log="PDF 匯出失敗",
        failure_prefix="匯出失敗：",
        missing_msg="PDF 檔案未產生",
    )


def _report_reference(row: dict, detail: dict, event_type: str) -> str:
    if event_type == "VISIT":
        return _plain_cell(row.get("event_id") or detail.get("visit_date") or row.get("event_date"))
    return _plain_cell(detail.get("anomaly_no") or row.get("ref_no") or row.get("event_id"))


def _anomaly_attachment_block(anomaly_id: object) -> str:
    key = str(anomaly_id or "").strip()
    if not key:
        return ""
    paths = attachment_manager.list_anomaly_attachments(key)
    if not paths:
        return ""
    captions = attachment_manager.get_anomaly_captions(key)
    cards: list[str] = []

    for path in paths:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        display_width, display_height = _attachment_display_size(path)
        suffix = path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        b64 = base64.b64encode(data).decode("ascii")
        caption_text = (captions.get(path.name) or "").strip()
        caption_html = ""
        if caption_text:
            caption_html = (
                f'<div style="font-size:9pt;color:{_TEXT_SECONDARY};'
                'margin-top:4px;font-style:italic;line-height:1.3;">'
                f"{escape(caption_text)}</div>"
            )
        cards.append(
            '<table width="100%" cellspacing="0" cellpadding="0" '
            'style="page-break-inside:avoid;width:100%;">'
            '<tr>'
            '<td align="center" '
            'style="padding:16px 14px 18px 14px;vertical-align:top;">'
            f'<div style="border:1px solid {_BORDER};padding:7px;background:#ffffff;display:inline-block;">'
            f'<img src="data:{mime};base64,{b64}" '
            f'width="{display_width}" height="{display_height}" '
            'style="display:block;margin:0 auto;" />'
            '</div>'
            f'<div style="font-size:9.5pt;color:{_TEXT_PRIMARY};'
            'font-weight:700;margin-top:8px;">'
            f"{escape(path.name)}</div>"
            f"{caption_html}"
            "</td>"
            "</tr>"
            "</table>"
        )
    if not cards:
        return ""

    return (
        '<div class="section-breakable">'
        '<div class="section-title">附件照片</div>'
        f'{"".join(cards)}'
        "</div>"
    )


def _linked_visit_inline(row: dict, linked_visit: dict | None) -> str:
    visit_date = str(_linked_visit_date(row, linked_visit) or "").strip() or "-"
    summary = str((linked_visit or {}).get("summary") or "").strip()
    html = f'<span class="linked-visit-date">{escape(visit_date)}</span>'
    if summary:
        html += (
            '<span class="linked-visit-sep">&nbsp;&nbsp;|&nbsp;&nbsp;</span>'
            f'<span class="linked-visit-summary">{escape(summary)}</span>'
        )
    return html


def _visit_defect_notes_section(detail: dict) -> str:
    product_sections = [
        item
        for item in detail.get("product_sections") or []
        if isinstance(item, dict)
    ]
    notes = [
        item
        for item in detail.get("defect_notes") or []
        if isinstance(item, dict)
    ]
    if not product_sections and not notes:
        return ""

    visit_level_notes = [
        note
        for note in notes
        if not str(note.get("visit_product_section_id") or "").strip()
    ]
    section_notes: dict[str, list[dict]] = {}
    for note in notes:
        section_id = str(note.get("visit_product_section_id") or "").strip()
        if section_id:
            section_notes.setdefault(section_id, []).append(note)

    blocks: list[str] = []
    if visit_level_notes:
        blocks.append(
            _visit_defect_note_block("共通現場缺失", "", visit_level_notes)
        )

    for index, section in enumerate(product_sections, start=1):
        section_id = str(section.get("id") or "").strip()
        title = (
            str(section.get("product_name") or "").strip()
            or str(section.get("product_code") or "").strip()
            or f"產品區段 {index}"
        )
        meta_parts = [
            ("時段", section.get("time_slot")),
            ("工單", section.get("work_order_no")),
            ("數量", _positive_number_or_dash(section.get("production_qty"))),
            ("摘要", section.get("summary")),
        ]
        meta_text = " / ".join(
            f"{label}: {_plain_cell(value)}"
            for label, value in meta_parts
            if _plain_cell(value) != "-"
        )
        blocks.append(
            _visit_defect_note_block(
                title,
                meta_text,
                section_notes.get(section_id, []),
            )
        )

    return (
        '<div class="section-breakable">'
        '<div class="section-title">缺失與改善紀錄</div>'
        f'{"".join(blocks)}'
        "</div>"
    )


def _visit_defect_note_block(
    title: str,
    meta_text: str,
    notes: list[dict],
) -> str:
    meta_html = (
        f'<div class="visit-product-meta">{escape(meta_text)}</div>'
        if meta_text
        else ""
    )
    rows: list[str] = []
    for note in notes:
        improvement = str(note.get("improvement_desc") or "").strip()
        improvement_text = improvement or "待補改善"
        rows.append(
            "<tr>"
            f'<td width="34%">{_cell(note.get("defect_desc"))}</td>'
            f'<td width="34%">{_cell(improvement_text)}</td>'
            f'<td width="32%">{_cell(note.get("note"))}</td>'
            "</tr>"
        )
    if rows:
        table_html = (
            '<table class="visit-defect-table" width="100%" '
            'cellspacing="0" cellpadding="0">'
            "<tr><th width=\"34%\">缺失內容</th>"
            "<th width=\"34%\">改善內容</th>"
            "<th width=\"32%\">備註</th></tr>"
            f'{"".join(rows)}</table>'
        )
    else:
        table_html = '<div class="visit-defect-empty">此產品區段尚未記錄缺失。</div>'
    return (
        '<div class="visit-product-block">'
        f'<div class="visit-product-title">{escape(title)}</div>'
        f"{meta_html}{table_html}</div>"
    )


def _linked_visit_date(row: dict, linked_visit: dict | None) -> object:
    if linked_visit is not None:
        return linked_visit.get("visit_date")
    return row.get("linked_visit_date")


def _current_action_display(current: object) -> str:
    if not isinstance(current, dict):
        return "—"
    description = str(current.get("description") or "").strip()
    if not description:
        return "—"
    owner = str(current.get("owner") or "").strip() or "—"
    due = str(current.get("due_date") or "").strip()
    if due:
        return f"{description}（{owner} / {due}）"
    return f"{description}（{owner}）"


def _quality_overview_section(overview: dict, open_actions: list[dict]) -> str:
    from database.repo_helpers import CASE_ACTION_OPEN_STATUSES

    fields: list[tuple[str, object]] = [
        ("逾期", "是" if overview.get("overdue") else "否"),
        ("目前處置", _current_action_display(overview.get("current_action"))),
        ("進行中處置數", int(overview.get("open_action_count") or 0)),
        ("根本原因狀態", overview.get("root_cause_status") or "尚未開始"),
        ("改善措施狀態", overview.get("corrective_action_status") or "—"),
        ("有效性驗證", overview.get("verification_result") or "—"),
        ("原因假設數", int(overview.get("hypothesis_count") or 0)),
        ("附件數", int(overview.get("attachment_count") or 0)),
    ]
    html = _section("品質結論／目前處置", fields)
    open_rows = [
        action
        for action in open_actions
        if action.get("execution_status") in CASE_ACTION_OPEN_STATUSES
    ]
    if open_rows:
        lines = []
        for action in open_rows:
            action_type = str(action.get("action_type") or "").strip()
            description = str(action.get("description") or "").strip()
            owner = str(action.get("owner") or "").strip() or "—"
            due = str(action.get("due_date") or "").strip() or "—"
            lines.append(f"{action_type}：{description}（{owner} / {due}）")
        html += _text_section("開啟中處置", "\n".join(lines))
    return html


def _hypothesis_tree_section(hypotheses: list[dict], *, include_png: bool) -> str:
    if not hypotheses:
        return ""
    from services.event._hypothesis_tree_png import (
        format_hypothesis_tree_text,
        render_hypothesis_tree_png,
    )

    text_body = format_hypothesis_tree_text(hypotheses)
    if include_png:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            png_path = Path(tmp.name)
        if render_hypothesis_tree_png(hypotheses, png_path):
            try:
                data = png_path.read_bytes()
            except OSError:
                data = b""
            finally:
                try:
                    png_path.unlink(missing_ok=True)
                except OSError:
                    pass
            if data:
                b64 = base64.b64encode(data).decode("ascii")
                return (
                    '<div class="section-breakable">'
                    '<div class="section-title">原因假設樹</div>'
                    '<table width="100%" cellspacing="0" cellpadding="0" '
                    'style="page-break-inside:avoid;width:100%;">'
                    "<tr><td align=\"center\" style=\"padding:12px;\">"
                    f'<img src="data:image/png;base64,{b64}" width="480" '
                    'style="display:block;margin:0 auto;" />'
                    "</td></tr></table>"
                    "</div>"
                )
    return _text_section("原因假設樹", text_body)


def _anomaly_export_enrichment(anomaly_id: str) -> tuple[dict, list[dict], list[dict]]:
    from services.event import _anomaly_workbench_service
    from services.event import _case_action_service

    try:
        overview = _anomaly_workbench_service.get_overview_card(anomaly_id)
        actions = _case_action_service.list_case_actions(anomaly_id)
        hypotheses = _anomaly_workbench_service.list_hypotheses(anomaly_id)
    except ValueError:
        overview = {}
        actions = []
        hypotheses = []
    return overview, actions, hypotheses


def build_brief_event_pdf_html(
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
    exported_at: datetime | None = None,
) -> str:
    event_type, issued_at_text, reference_no, status_value = _event_report_context(
        row, detail, exported_at
    )

    if event_type == "VISIT":
        title = "供應商訪廠精簡報告"
        meta_lines = [
            ("訪廠日期", _plain_cell(detail.get("visit_date") or row.get("event_date"))),
        ]
        sections = [
            _section(
                "基本資料",
                [
                    ("日期", detail.get("visit_date")),
                    ("供應商", detail.get("supplier_name")),
                    ("訪廠人員", detail.get("visitor_name")),
                    ("品名", detail.get("product_name")),
                ],
                status_value=status_value,
            ),
            _text_section("摘要", detail.get("summary")),
        ]
        defect_note_section = _visit_defect_notes_section(detail)
        if defect_note_section:
            sections.append(defect_note_section)
    else:
        title = "供應商異常處理精簡報告"
        meta_lines = [
            ("異常案號", _plain_cell(reference_no)),
        ]

        anomaly_fields: list[tuple[str, object]] = [
            ("日期", detail.get("anomaly_date") or row.get("event_date")),
            ("供應商", detail.get("supplier_name")),
            ("品名", detail.get("product_name")),
            ("責任人", detail.get("responsible_person")),
            ("預計回覆日", detail.get("due_date")),
        ]

        sections = [
            _section(
                "基本資料",
                anomaly_fields,
            ),
            _text_section("問題描述", detail.get("problem_desc") or row.get("content")),
        ]

        closing_section = _closing_info_section(
            detail,
            status_value,
            [
                ("結案日", detail.get("closed_at")),
                ("改善說明", detail.get("improvement_desc")),
            ],
        )
        if closing_section:
            sections.append(closing_section)

    body = _assemble_report_body(issued_at_text, sections)
    return _brief_html_document(title, body, _preferred_pdf_font_family(), meta_lines)


def export_brief_event_pdf(
    path: str | Path,
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
) -> tuple[bool, str]:
    return _export_html_pdf(
        path,
        lambda: build_brief_event_pdf_html(row, detail, linked_visit=linked_visit),
        success_prefix="已匯出精簡版至：",
        failure_log="精簡版 PDF 匯出失敗",
        failure_prefix="匯出精簡版失敗：",
        missing_msg="精簡版 PDF 檔案未產生",
    )


def render_brief_event_to_image(
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
) -> QImage | None:
    """將精簡報告 HTML 渲染為手機卡片 QImage，供 LINE 剪貼簿圖片貼上使用。

    尺寸為 3:4 手機卡片 (1080×1440 px)，針對 LINE 行動端閱讀最佳化。
    Returns ``None`` on failure.
    """
    try:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QImage, QPainter

        # 手機卡片寬度固定為 1080，高度動態計算，底限為 1440
        PAGE_W = 1080

        html = build_brief_event_pdf_html(row, detail, linked_visit=linked_visit)

        doc = QTextDocument()
        doc.setDocumentMargin(0)  # 徹底清除 QTextDocument 預設的白邊
        font_family = _preferred_pdf_font_family()
        doc.setDefaultFont(QFont(font_family, 14))
        doc.setHtml(html)
        doc.setTextWidth(PAGE_W)

        # 動態計算實際內容渲染高度，防止文字溢出與截斷
        doc_height = doc.size().height()
        PAGE_H = int(doc_height)

        # 使用 ARGB32，並以白色底色填滿，使卡片背景色彩一致
        image = QImage(PAGE_W, PAGE_H, QImage.Format.Format_ARGB32)
        image.fill(QColor("#ffffff"))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 滿版繪製，由 HTML 內部表格與 padding 自行控制邊距，避免強行平移產生白邊
        clip_rect = QRectF(0, 0, PAGE_W, PAGE_H)
        doc.drawContents(painter, clip_rect)

        # 強行在最外圍繪製一圈 #ffffff 的邊框，徹底覆蓋任何 Qt 邊界對齊所產生的極細白線
        from PySide6.QtGui import QPen
        pen = QPen(QColor("#ffffff"), 4)
        painter.setPen(pen)
        painter.drawRect(0, 0, PAGE_W, PAGE_H)

        painter.end()

        return image
    except Exception:
        logger.exception("渲染精簡報告圖片失敗")
        return None
