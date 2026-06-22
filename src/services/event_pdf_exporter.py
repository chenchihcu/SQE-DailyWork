from __future__ import annotations

import base64
import logging
import re
from datetime import datetime
from html import escape
from os import environ
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont, QFontDatabase, QTextDocument

from services import attachment_manager


_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_LOADED_FONT_FAMILY: str | None = None
_LOGO_DATA_URI: str | None = None

_BRAND_PRIMARY = "#065977"
_BRAND_SECONDARY = "#0274BE"
_TEXT_PRIMARY = "#1F2937"
_TEXT_SECONDARY = "#475569"
_BORDER = "#D9E2EA"
_PANEL_BG = "#F8FAFC"
_LABEL_BG = "#EEF6FA"
_CHIP_EMPTY_BG = "#94A3B8"
_ATTACHMENT_MAX_WIDTH_PX = 660
_ATTACHMENT_MAX_HEIGHT_PX = 780

_NUMBERED_PARAGRAPH = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:[.)、．])?(?=\s|$)")

_STATUS_NOT_PROVIDED: object = object()


class _RawHtml(str):
    """Marker subclass: pass through pre-rendered HTML without escaping."""


def sanitize_filename_part(value: object, *, fallback: str = "未命名") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("_", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned or fallback


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


def build_event_pdf_html(
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
    exported_at: datetime | None = None,
) -> str:
    event_type = _event_type(row)
    issued_at = exported_at or datetime.now()
    issued_at_text = issued_at.strftime("%Y-%m-%d %H:%M:%S")
    reference_no = _report_reference(row, detail, event_type)
    status_value = detail.get("status") or row.get("status")

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
                    ("訪廠人員", detail.get("visitor_name")),
                    ("品名", detail.get("product_name")),
                    ("階段", detail.get("product_stage")),
                    ("工單", detail.get("work_order_no")),
                    ("數量", _positive_number_or_dash(detail.get("production_qty"))),
                ],
                status_value=status_value,
            ),
            _tech_transfer_section(detail),
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
            ("供應商", detail.get("supplier_name")),
            ("品名", detail.get("product_name")),
            ("階段", detail.get("product_stage")),
            ("工單", detail.get("outsource_work_order") or row.get("work_order_no")),
            ("數量", _positive_number_or_dash(detail.get("batch_qty"))),
            ("技轉訪廠", "是" if detail.get("is_tech_transfer") else "否"),
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
        if linked_visit:
            sections.append(_tech_transfer_section(linked_visit))
        sections.append(
            _text_section("問題描述", detail.get("problem_desc") or row.get("content"))
        )
        if str(detail.get("pending_items") or "").strip():
            sections.append(
                _text_section("確認事項", detail.get("pending_items"))
            )

        if str(status_value or "").strip() == "已結案" or detail.get("improvement_desc"):
            sections.append(
                _section(
                    "結案資訊",
                    [
                        ("結案日", detail.get("closed_at")),
                        ("結案人員", detail.get("closed_by")),
                        ("原因分類", detail.get("root_cause_category")),
                        ("改善說明", detail.get("improvement_desc")),
                    ],
                )
            )
        attachment_html = _anomaly_attachment_block(
            detail.get("id") or row.get("id")
        )
        if attachment_html:
            sections.append(attachment_html)

    body = "".join(
        [
            _summary_panel(
                [
                    ("列印時間", issued_at_text, "text"),
                ]
            ),
            *sections,
        ]
    )
    return _html_document(title, body, _preferred_pdf_font_family(), meta_lines)


def export_event_pdf(
    path: str | Path,
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
) -> tuple[bool, str]:
    try:
        output = Path(path)
        if output.suffix.lower() != ".pdf":
            output = output.with_suffix(".pdf")
        output.parent.mkdir(parents=True, exist_ok=True)

        html = build_event_pdf_html(row, detail, linked_visit=linked_visit)
        _write_html_pdf(html, output)
        if not output.exists() or output.stat().st_size <= 0:
            raise RuntimeError("PDF 檔案未產生")
        return True, f"已匯出至：{output}"
    except Exception as exc:
        logger.exception("PDF 匯出失敗")
        return False, f"匯出失敗：{exc}"


def _event_type(row: dict) -> str:
    event_type = str(row.get("event_type") or "").strip().upper()
    if event_type not in {"VISIT", "ANOMALY"}:
        raise ValueError("Event type is required")
    return event_type


def _write_html_pdf(html: str, output: Path) -> None:
    from xhtml2pdf import pisa

    with open(output, "wb") as f:
        status = pisa.CreatePDF(html, dest=f)
    if status.err:
        raise RuntimeError(f"PDF 轉換失敗: {status.err}")


def _preferred_pdf_font_family() -> str:
    global _LOADED_FONT_FAMILY
    if _LOADED_FONT_FAMILY:
        return _LOADED_FONT_FAMILY

    for path in _font_candidate_paths():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _LOADED_FONT_FAMILY = families[0]
            return _LOADED_FONT_FAMILY

    for family in (
        "Microsoft JhengHei",
        "Noto Sans TC",
        "PMingLiU",
        "Arial",
    ):
        if family in QFontDatabase.families():
            _LOADED_FONT_FAMILY = family
            return _LOADED_FONT_FAMILY

    _LOADED_FONT_FAMILY = "sans-serif"
    return _LOADED_FONT_FAMILY


def _font_candidate_paths() -> tuple[Path, ...]:
    fonts_dir = Path(environ.get("WINDIR", str(Path.home().drive) + r"\Windows")) / "Fonts"
    return (
        fonts_dir / "msjh.ttc",
        fonts_dir / "mingliu.ttc",
        fonts_dir / "kaiu.ttf",
        fonts_dir / "NotoSansTC-VF.ttf",
        fonts_dir / "arial.ttf",
    )


def _html_document(
    title: str,
    body: str,
    font_family: str,
    meta_lines: list[tuple[str, str]] | None = None,
) -> str:
    css_font_family = escape(font_family, quote=True)
    logo_html = _logo_html()
    meta_html = _document_meta_html(meta_lines or [])
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{
  background: #ffffff;
}}
body {{
  color: {_TEXT_PRIMARY};
  font-family: "{css_font_family}", "Microsoft JhengHei", "Noto Sans TC", sans-serif;
  font-size: 10pt;
}}
.brand-topline-1 {{
  background: {_BRAND_PRIMARY};
  height: 3px;
}}
.brand-topline-2 {{
  background: {_BRAND_SECONDARY};
  height: 1px;
  margin-bottom: 14px;
}}
.report-header {{
  border-collapse: collapse;
  margin-bottom: 12px;
  width: 100%;
}}
.report-header td {{
  border: 0;
  padding: 0;
  vertical-align: middle;
}}
.logo-cell {{
  width: 56%;
}}
.logo-cell img {{
  height: 44px;
  width: auto;
}}
.logo-fallback {{
  color: {_BRAND_PRIMARY};
  font-size: 24pt;
  font-weight: 700;
}}
.company-name {{
  color: #64748B;
  font-size: 8.4pt;
  margin-top: 6px;
}}
.document-meta {{
  color: #64748B;
  font-size: 10pt;
  line-height: 1.4;
  text-align: right;
  width: 44%;
}}
.document-meta-key {{
  color: #64748B;
  font-size: 8.5pt;
  font-weight: 500;
}}
.document-meta-value {{
  color: {_TEXT_PRIMARY};
  font-size: 12pt;
  font-weight: 700;
  letter-spacing: 0.5px;
}}
.title-band {{
  background: {_BRAND_PRIMARY};
  border-bottom: 3px solid {_BRAND_SECONDARY};
  color: #ffffff;
  font-size: 18pt;
  font-weight: 700;
  margin-top: 4px;
  padding: 11px 16px;
}}
.summary {{
  border-collapse: collapse;
  margin-top: 12px;
  page-break-inside: avoid;
  width: 100%;
}}
.summary td {{
  background: {_PANEL_BG};
  border: 1px solid {_BORDER};
  padding: 10px 12px;
  vertical-align: middle;
  width: 33%;
}}
.summary-label {{
  color: {_TEXT_SECONDARY};
  font-size: 8.4pt;
  font-weight: 700;
  margin-bottom: 6px;
}}
.summary-value {{
  color: {_TEXT_PRIMARY};
  font-size: 11pt;
  font-weight: 700;
  word-break: break-word;
  word-wrap: break-word;
}}
.section {{
  background: #ffffff;
  border: 1px solid {_BORDER};
  margin-top: 12px;
  page-break-inside: avoid;
}}
.section-breakable {{
  background: #ffffff;
  border: 1px solid {_BORDER};
  margin-top: 12px;
  page-break-inside: auto;
}}
.section-title {{
  background: {_PANEL_BG};
  border-bottom: 1px solid {_BORDER};
  border-left: 4px solid {_BRAND_PRIMARY};
  color: {_BRAND_PRIMARY};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 8px 11px;
  page-break-after: avoid;
}}
table {{
  background: #ffffff;
  border-collapse: collapse;
  width: 100%;
}}
td {{
  background: #ffffff;
  border-top: 1px solid {_BORDER};
  padding: 7px 9px;
  vertical-align: top;
}}
td.label {{
  background: {_LABEL_BG};
  color: {_TEXT_SECONDARY};
  font-weight: 700;
  width: 18%;
}}
td.value {{
  color: {_TEXT_PRIMARY};
  width: 32%;
  word-break: break-word;
  word-wrap: break-word;
}}
td.value-wide {{
  color: {_TEXT_PRIMARY};
  word-break: break-word;
  word-wrap: break-word;
}}
.status-chip {{
  background: {_BRAND_PRIMARY};
  border-radius: 10px;
  color: #ffffff;
  display: inline-block;
  font-weight: 700;
  padding: 2px 12px;
}}
.status-chip-empty {{
  background: {_CHIP_EMPTY_BG};
}}
.tech-chip {{
  border-radius: 10px;
  display: inline-block;
  font-weight: 700;
  padding: 2px 12px;
}}
.tech-chip-yes {{
  background: #DCFCE7;
  border: 1px solid #16A34A;
  color: #166534;
}}
.tech-chip-no {{
  background: #F1F5F9;
  border: 1px solid #94A3B8;
  color: #475569;
}}
.yes-check {{
  color: #16A34A;
  font-weight: 700;
}}
.no-mark {{
  color: #94A3B8;
}}
.linked-visit-date {{
  color: {_TEXT_PRIMARY};
  font-weight: 700;
  margin-right: 8px;
}}
.linked-visit-summary {{
  color: {_TEXT_SECONDARY};
}}
.visit-product-block {{
  border-top: 1px solid {_BORDER};
  padding: 10px 12px 12px;
  page-break-inside: avoid;
}}
.visit-product-title {{
  color: {_BRAND_PRIMARY};
  font-weight: 700;
  margin-bottom: 4px;
}}
.visit-product-meta {{
  color: {_TEXT_SECONDARY};
  font-size: 8.5pt;
  margin-bottom: 8px;
}}
.visit-defect-table th {{
  background: {_LABEL_BG};
  border-top: 1px solid {_BORDER};
  color: {_TEXT_SECONDARY};
  font-weight: 700;
  padding: 7px 9px;
  text-align: left;
}}
.visit-defect-table td {{
  color: {_TEXT_PRIMARY};
  line-height: 1.45;
}}
.visit-defect-empty {{
  color: {_TEXT_SECONDARY};
  padding: 7px 9px;
}}
.text-block {{
  background: #ffffff;
  border-top: 1px solid {_BORDER};
  line-height: 1.55;
  min-height: 42px;
  padding: 12px 14px;
}}
.paragraph-line {{
  margin-top: 4px;
}}
.paragraph-item {{
  border-left: 3px solid {_BRAND_PRIMARY};
  color: {_TEXT_PRIMARY};
  font-weight: 700;
  margin-top: 9px;
  padding-left: 9px;
}}
.paragraph-subitem {{
  color: {_TEXT_SECONDARY};
  margin-left: 28px;
}}
.paragraph-body {{
  color: {_TEXT_PRIMARY};
  padding-left: 2px;
}}
.footer {{
  border-top: 1px solid {_BORDER};
  color: #94A3B8;
  font-size: 8pt;
  margin-top: 36px;
  padding-top: 10px;
  text-align: center;
}}
.footer-text {{
  letter-spacing: 0.3px;
}}
.page-number {{
  float: right;
}}
</style>
</head>
<body>
<div class="brand-topline-1"></div>
<div class="brand-topline-2"></div>
<table class="report-header" width="100%" cellspacing="0" cellpadding="0">
  <tr>
    <td class="logo-cell" width="50%" valign="middle" align="left">
      {logo_html}
      <div class="company-name">Medical Intubation Technology Corporation</div>
    </td>
    <td class="document-meta" width="50%" valign="middle" align="right">
      {meta_html}
    </td>
  </tr>
</table>
<div class="title-band">{escape(title)}</div>
{body}
<div class="footer">
  <span class="footer-text">MITCORP / SQE Quality Report &nbsp;&bull;&nbsp; Generated by SQE DailyWork</span>
  <span class="page-number">1</span>
</div>
</body>
</html>
"""


def _brief_html_document(
    title: str,
    body: str,
    font_family: str,
    meta_lines: list[tuple[str, str]] | None = None,
) -> str:
    css_font_family = escape(font_family, quote=True)
    logo_html = _logo_html()
    meta_html = _document_meta_html(meta_lines or [])
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
  background-color: #ffffff;
  color: #111111;
  font-family: "{css_font_family}", "Microsoft JhengHei", "Noto Sans TC", sans-serif;
  font-size: 14pt;
  margin: 0;
  padding: 0;
}}
.card-outer {{
  background-color: #ffffff;
  width: 100%;
}}
.card-inner {{
  background-color: #ffffff;
  border: 1px solid #111111;
}}
.card-content {{
  padding: 24px;
}}
.brand-topline-1 {{
  background: #111111;
  height: 3px;
}}
.brand-topline-2 {{
  display: none;
}}
.report-header {{
  border-collapse: collapse;
  margin-bottom: 18px;
  width: 100%;
}}
.report-header td {{
  border: 0;
  padding: 0;
  vertical-align: middle;
}}
.logo-cell {{
  width: 56%;
}}
.logo-cell img {{
  height: 56px;
  width: auto;
  filter: grayscale(100%);
}}
.logo-fallback {{
  color: #111111;
  font-size: 28pt;
  font-weight: 700;
}}
.company-name {{
  color: #666666;
  font-size: 11pt;
  margin-top: 8px;
}}
.document-meta {{
  color: #666666;
  font-size: 13pt;
  line-height: 1.5;
  text-align: right;
  width: 44%;
}}
.document-meta-key {{
  color: #666666;
  font-size: 11pt;
  font-weight: 500;
}}
.document-meta-value {{
  color: #111111;
  font-size: 15pt;
  font-weight: 700;
  letter-spacing: 0.5px;
}}
.title-band {{
  background: #ffffff;
  border-bottom: 2px solid #111111;
  color: #111111;
  font-size: 22pt;
  font-weight: 700;
  margin-top: 8px;
  padding: 10px 0px;
}}
.summary {{
  border-collapse: collapse;
  margin-top: 18px;
  page-break-inside: avoid;
  width: 100%;
}}
.summary td {{
  background: #ffffff;
  border: 1px solid #111111;
  padding: 12px 14px;
  vertical-align: middle;
  width: 33%;
}}
.summary-label {{
  color: #666666;
  font-size: 11pt;
  font-weight: 700;
  margin-bottom: 6px;
}}
.summary-value {{
  color: #111111;
  font-size: 14pt;
  font-weight: 700;
  word-break: break-word;
  word-wrap: break-word;
}}
.section {{
  background: #ffffff;
  border: 1px solid #111111;
  margin-top: 18px;
  page-break-inside: avoid;
}}
.section-breakable {{
  background: #ffffff;
  border: 1px solid #111111;
  margin-top: 18px;
  page-break-inside: auto;
}}
.section-title {{
  background: #ffffff;
  border-bottom: 1px solid #111111;
  border-left: none;
  color: #111111;
  font-size: 15pt;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 8px 0px;
  page-break-after: avoid;
}}
table {{
  background: #ffffff;
  border-collapse: collapse;
  width: 100%;
}}
table td {{
  background: #ffffff;
  border-top: 1px solid #E2E8F0;
  padding: 10px 12px;
  vertical-align: top;
  font-size: 13pt;
}}
table td.label {{
  background: #F8FAFC;
  color: #111111;
  font-weight: 700;
  width: 20%;
}}
table td.value {{
  color: #111111;
  width: 30%;
  word-break: break-word;
  word-wrap: break-word;
}}
table td.value-wide {{
  color: #111111;
  word-break: break-word;
  word-wrap: break-word;
}}
.status-chip {{
  background: #ffffff;
  border: 1px solid #111111;
  border-radius: 4px;
  color: #111111;
  display: inline-block;
  font-weight: 700;
  padding: 3px 14px;
  font-size: 12pt;
}}
.status-chip-empty {{
  background: #ffffff;
  border: 1px solid #CCCCCC;
  color: #666666;
  border-radius: 4px;
}}
.tech-chip {{
  border-radius: 4px;
  display: inline-block;
  font-weight: 700;
  padding: 3px 14px;
  font-size: 12pt;
}}
.tech-chip-yes {{
  background: #ffffff;
  border: 1px solid #111111;
  color: #111111;
}}
.tech-chip-no {{
  background: #ffffff;
  border: 1px solid #CCCCCC;
  color: #666666;
}}
.yes-check {{
  color: #111111;
  font-weight: 700;
}}
.no-mark {{
  color: #CCCCCC;
}}
.linked-visit-date {{
  color: #111111;
  font-weight: 700;
  margin-right: 10px;
  font-size: 13pt;
}}
.linked-visit-summary {{
  color: #666666;
  font-size: 13pt;
}}
.visit-product-block {{
  border-top: 1px solid #E2E8F0;
  padding: 12px 14px;
  page-break-inside: avoid;
}}
.visit-product-title {{
  color: #111111;
  font-weight: 700;
  margin-bottom: 6px;
  font-size: 14pt;
}}
.visit-product-meta {{
  color: #666666;
  font-size: 11pt;
  margin-bottom: 10px;
}}
.visit-defect-table th {{
  background: #F8FAFC;
  border-top: 1px solid #E2E8F0;
  color: #666666;
  font-weight: 700;
  padding: 8px 10px;
  text-align: left;
  font-size: 12pt;
}}
.visit-defect-table td {{
  color: #111111;
  line-height: 1.5;
  font-size: 13pt;
}}
.visit-defect-empty {{
  color: #666666;
  padding: 8px 10px;
  font-size: 13pt;
}}
.text-block {{
  background: #ffffff;
  border-top: 1px solid #E2E8F0;
  line-height: 1.6;
  min-height: 50px;
  padding: 14px 16px;
  font-size: 13pt;
}}
.paragraph-line {{
  margin-top: 6px;
}}
.paragraph-item {{
  border-left: 4px solid #111111;
  color: #111111;
  font-weight: 700;
  margin-top: 10px;
  padding-left: 10px;
  font-size: 13pt;
}}
.paragraph-subitem {{
  color: #666666;
  margin-left: 28px;
  font-size: 12pt;
}}
.paragraph-body {{
  color: #111111;
  padding-left: 2px;
  font-size: 13pt;
}}
.footer {{
  border-top: 1px solid #E2E8F0;
  color: #999999;
  font-size: 10pt;
  margin-top: 36px;
  padding-top: 12px;
  text-align: center;
}}
.footer-text {{
  letter-spacing: 0.4px;
}}
</style>
</head>
<body>
<table class="card-outer" width="100%" cellspacing="0" cellpadding="24" border="0">
  <tr>
    <td align="center" valign="top">
      <table class="card-inner" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td class="card-content" align="left" valign="top">
            <div class="brand-topline-1"></div>
            <div class="brand-topline-2"></div>
            <table class="report-header" width="100%" cellspacing="0" cellpadding="0">
              <tr>
                <td class="logo-cell" width="50%" valign="middle" align="left">
                  {logo_html}
                  <div class="company-name">Medical Intubation Technology Corporation</div>
                </td>
                <td class="document-meta" width="50%" valign="middle" align="right">
                  {meta_html}
                </td>
              </tr>
            </table>
            <div class="title-band">{escape(title)}</div>
            {body}
            <div class="footer">
              <span class="footer-text">MITCORP / SQE Quality Report &nbsp;&bull;&nbsp; Generated by SQE DailyWork</span>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""


def _document_meta_html(meta_lines: list[tuple[str, str]]) -> str:
    if not meta_lines:
        return ""
    parts: list[str] = []
    for label, value in meta_lines:
        label_text = escape(str(label or "").strip())
        value_text = escape(str(value or "").strip())
        if value_text:
            parts.append(
                f'<span class="document-meta-key">{label_text}</span>'
                "<br>"
                f'<span class="document-meta-value">{value_text}</span>'
            )
    return "<br>".join(parts)


def _logo_html() -> str:
    logo_uri = _logo_data_uri()
    if not logo_uri:
        return '<div class="logo-fallback">Mitcorp</div>'
    return f'<img src="{logo_uri}" alt="Mitcorp">'


def _logo_data_uri() -> str:
    global _LOGO_DATA_URI
    if _LOGO_DATA_URI is not None:
        return _LOGO_DATA_URI

    logo_path = Path(__file__).resolve().parent / "assets" / "mitcorp_logo.png"
    try:
        logo_bytes = logo_path.read_bytes()
    except OSError:
        _LOGO_DATA_URI = ""
        return _LOGO_DATA_URI

    encoded = base64.b64encode(logo_bytes).decode("ascii")
    _LOGO_DATA_URI = f"data:image/png;base64,{encoded}"
    return _LOGO_DATA_URI


def _summary_panel(items: list[tuple[str, object, str]]) -> str:
    cells: list[str] = []
    for label, value, kind in items:
        if kind == "status":
            value_html = _status_badge(value, font_size="11pt")
        else:
            value_html = _cell(value)
        cells.append(
            "<td>"
            f'<div class="summary-label">{escape(label)}</div>'
            f'<div class="summary-value">{value_html}</div>'
            "</td>"
        )
    return (
        '<table class="summary" width="100%" cellspacing="0" cellpadding="0">'
        f'<tr>{"".join(cells)}</tr></table>'
    )


def _status_badge(value: object, *, font_size: str = "10pt") -> str:
    text = str(value or "").strip()
    if not text:
        return (
            '<span class="status-chip status-chip-empty" '
            f'style="font-size:{font_size}">-</span>'
        )
    return (
        f'<span class="status-chip" style="font-size:{font_size}">'
        f"{escape(text)}</span>"
    )


def _section(
    title: str,
    fields: list[tuple[str, object]],
    *,
    status_value: object = _STATUS_NOT_PROVIDED,
    extra_rows: list[str] | None = None,
) -> str:
    rows: list[str] = []
    for idx in range(0, len(fields), 2):
        left = fields[idx]
        right = fields[idx + 1] if idx + 1 < len(fields) else ("", "")
        right_label = _cell(right[0]) if str(right[0] or "").strip() else ""
        right_value = _cell(right[1]) if str(right[0] or "").strip() else ""
        rows.append(
            "<tr>"
            f'<td class="label" width="18%">{_cell(left[0])}</td>'
            f'<td class="value" width="32%">{_cell(left[1])}</td>'
            f'<td class="label" width="18%">{right_label}</td>'
            f'<td class="value" width="32%">{right_value}</td>'
            "</tr>"
        )
    if status_value is not _STATUS_NOT_PROVIDED:
        rows.append(
            "<tr>"
            '<td class="label" width="18%">狀態</td>'
            f'<td class="value-wide" colspan="3">{_status_badge(status_value)}</td>'
            "</tr>"
        )
    if extra_rows:
        rows.extend(extra_rows)
    return (
        '<div class="section">'
        f'<div class="section-title">{escape(title)}</div>'
        f'<table width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'
        "</div>"
    )


def _wide_row(label: str, value_html: str) -> str:
    return (
        "<tr>"
        f'<td class="label" width="18%">{escape(label)}</td>'
        f'<td class="value-wide" colspan="3">{value_html}</td>'
        "</tr>"
    )


def _image_pixel_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except Exception:
        logger.exception("讀取圖片尺寸失敗 %s", path)
        return None


def _attachment_display_size(path: Path) -> tuple[int, int]:
    size = _image_pixel_size(path)
    if size is None:
        return _ATTACHMENT_MAX_WIDTH_PX, _ATTACHMENT_MAX_HEIGHT_PX

    source_width, source_height = size
    scale = min(
        _ATTACHMENT_MAX_WIDTH_PX / source_width,
        _ATTACHMENT_MAX_HEIGHT_PX / source_height,
    )
    width = max(1, round(source_width * scale))
    height = max(1, round(source_height * scale))
    return width, height


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
            'font-weight:600;margin-top:8px;">'
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


def _text_section(title: str, value: object) -> str:
    return (
        '<div class="section">'
        f'<div class="section-title">{escape(title)}</div>'
        f'<div class="text-block">{_structured_multiline(value)}</div>'
        "</div>"
    )


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


def _report_reference(row: dict, detail: dict, event_type: str) -> str:
    if event_type == "VISIT":
        return _plain_cell(row.get("event_id") or detail.get("visit_date") or row.get("event_date"))
    return _plain_cell(detail.get("anomaly_no") or row.get("ref_no") or row.get("event_id"))


def _cell(value: object) -> str:
    if isinstance(value, _RawHtml):
        return str(value) or "-"
    text = str(value or "").strip()
    return escape(text or "-")


def _plain_cell(value: object) -> str:
    text = str(value or "").strip()
    return text or "-"


def _structured_multiline(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return '<div class="paragraph-line paragraph-body paragraph-first">-</div>'

    lines = []
    for idx, line in enumerate(text.splitlines()):
        normalized = line.strip()
        if not normalized:
            continue
        line_class = _paragraph_line_class(normalized)
        classes = ["paragraph-line", line_class]
        if idx == 0:
            classes.append("paragraph-first")
        if line_class == "paragraph-subitem":
            # No bullets for numbered sub-items, just clean indentation
            content = escape(normalized)
        else:
            content = escape(normalized)
        lines.append(f'<div class="{" ".join(classes)}">{content}</div>')
    if not lines:
        return '<div class="paragraph-line paragraph-body paragraph-first">-</div>'
    return "".join(lines)


def _paragraph_line_class(text: str) -> str:
    match = _NUMBERED_PARAGRAPH.match(text)
    if not match:
        return "paragraph-body"
    return "paragraph-subitem" if "." in match.group(1) else "paragraph-item"


def _tech_state_marked(state: object, *, legacy_value: object = None) -> _RawHtml:
    """Render a tech-transfer item respecting tri-state ('yes'/'no'/'na').

    Falls back to the legacy boolean column when no state was stored — keeps
    older rows looking identical to before the migration.
    """
    text = str(state or "").strip().lower()
    if text not in ("yes", "no", "na"):
        text = "yes" if bool(legacy_value) else "no"
    if text == "yes":
        return _RawHtml('<span class="yes-check">&radic; 有</span>')
    if text == "na":
        return _RawHtml('<span class="no-mark">不適用</span>')
    return _RawHtml('<span class="no-mark">沒有</span>')


def _tech_status_badge(value: object) -> _RawHtml:
    if bool(value):
        return _RawHtml('<span class="tech-chip tech-chip-yes">已技轉</span>')
    return _RawHtml('<span class="tech-chip tech-chip-no">未技轉</span>')


def _tech_transfer_section(detail: dict) -> str:
    def cell(key: str) -> _RawHtml:
        return _tech_state_marked(
            detail.get(f"{key}_state"), legacy_value=detail.get(key)
        )

    return _section(
        "技轉項目",
        [
            ("技轉狀態", _tech_status_badge(detail.get("tech_transfer"))),
            ("作業標準書", cell("tech_transfer_doc")),
            ("載具要求", cell("carrier_requirement")),
            ("Underfill 要求", cell("dispensing_process")),
            ("電訊測試", cell("functional_test")),
            ("包裝規範", cell("packaging_requirement")),
        ],
    )


def _positive_number_or_dash(value: object) -> str:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return "-"
    return str(number) if number > 0 else "-"


def _linked_visit_date(row: dict, linked_visit: dict | None) -> object:
    if linked_visit is not None:
        return linked_visit.get("visit_date")
    return row.get("linked_visit_date")


def build_brief_event_pdf_html(
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
    exported_at: datetime | None = None,
) -> str:
    event_type = _event_type(row)
    issued_at = exported_at or datetime.now()
    issued_at_text = issued_at.strftime("%Y-%m-%d %H:%M:%S")
    reference_no = _report_reference(row, detail, event_type)
    status_value = detail.get("status") or row.get("status")

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

        if str(status_value or "").strip() == "已結案" or detail.get("improvement_desc"):
            sections.append(
                _section(
                    "結案資訊",
                    [
                        ("結案日", detail.get("closed_at")),
                        ("改善說明", detail.get("improvement_desc")),
                    ],
                )
            )

    body = "".join(
        [
            _summary_panel(
                [
                    ("列印時間", issued_at_text, "text"),
                ]
            ),
            *sections,
        ]
    )
    return _brief_html_document(title, body, _preferred_pdf_font_family(), meta_lines)


def export_brief_event_pdf(
    path: str | Path,
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
) -> tuple[bool, str]:
    try:
        output = Path(path)
        if output.suffix.lower() != ".pdf":
            output = output.with_suffix(".pdf")
        output.parent.mkdir(parents=True, exist_ok=True)

        html = build_brief_event_pdf_html(row, detail, linked_visit=linked_visit)
        _write_html_pdf(html, output)
        if not output.exists() or output.stat().st_size <= 0:
            raise RuntimeError("精簡版 PDF 檔案未產生")
        return True, f"已匯出精簡版至：{output}"
    except Exception as exc:
        logger.exception("精簡版 PDF 匯出失敗")
        return False, f"匯出精簡版失敗：{exc}"


def render_brief_event_to_image(
    row: dict,
    detail: dict,
    *,
    linked_visit: dict | None = None,
) -> "QImage | None":
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
