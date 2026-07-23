from __future__ import annotations

import base64
import functools
import logging
import re
from html import escape
from os import environ
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtGui import QFontDatabase

_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
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


def _write_html_pdf(html: str, output: Path) -> None:
    from xhtml2pdf import pisa

    with open(output, "wb") as f:
        status = pisa.CreatePDF(html, dest=f)
    if status.err:
        raise RuntimeError(f"PDF 轉換失敗: {status.err}")


def _font_candidate_paths() -> tuple[Path, ...]:
    fonts_dir = Path(environ.get("WINDIR", str(Path.home().drive) + r"\Windows")) / "Fonts"
    return (
        fonts_dir / "msjh.ttc",
        fonts_dir / "mingliu.ttc",
        fonts_dir / "kaiu.ttf",
        fonts_dir / "NotoSansTC-VF.ttf",
        fonts_dir / "arial.ttf",
    )


@functools.cache
def _preferred_pdf_font_family() -> str:
    import xhtml2pdf.default as pisa_default
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _font_candidate_paths():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            continue
        family_name = families[0]

        try:
            kwargs = {}
            if str(path).lower().endswith(".ttc"):
                kwargs["subfontIndex"] = 0
            ttfont = TTFont(family_name, str(path), **kwargs)
            pdfmetrics.registerFont(ttfont)

            key = family_name.lower()
            pisa_default.DEFAULT_FONT[key] = family_name
            pisa_default.DEFAULT_FONT[family_name] = family_name
            pisa_default.DEFAULT_FONT["microsoft jhenghei ui"] = family_name
            pisa_default.DEFAULT_FONT["microsoft jhenghei"] = family_name
            pisa_default.DEFAULT_FONT["noto sans tc"] = family_name
            pisa_default.DEFAULT_FONT["pmingliu"] = family_name
            pisa_default.DEFAULT_FONT["kaiu"] = family_name
            pisa_default.DEFAULT_FONT["sans-serif"] = family_name
            return family_name
        except Exception as e:
            logger.warning("Failed to register font %s for ReportLab: %s", path, e)
            return family_name

    for family in (
        "Microsoft JhengHei UI",
        "Microsoft JhengHei",
        "Noto Sans TC",
        "PMingLiU",
        "Arial",
    ):
        if family in QFontDatabase.families():
            return family

    return "sans-serif"


@functools.cache
def _logo_data_uri() -> str:
    logo_path = Path(__file__).resolve().parent / "assets" / "mitcorp_logo.png"
    try:
        logo_bytes = logo_path.read_bytes()
    except OSError:
        return ""

    encoded = base64.b64encode(logo_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _logo_html() -> str:
    logo_uri = _logo_data_uri()
    if not logo_uri:
        return '<div class="logo-fallback">Mitcorp</div>'
    return f'<img src="{logo_uri}" alt="Mitcorp">'


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
  font-weight: 400;
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
  font-weight: 400;
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


def _cell(value: object) -> str:
    if isinstance(value, _RawHtml):
        return str(value) or "-"
    text = str(value or "").strip()
    return escape(text or "-")


def _plain_cell(value: object) -> str:
    text = str(value or "").strip()
    return text or "-"


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


def _paragraph_line_class(text: str) -> str:
    match = _NUMBERED_PARAGRAPH.match(text)
    if not match:
        return "paragraph-body"
    return "paragraph-subitem" if "." in match.group(1) else "paragraph-item"


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


def _text_section(title: str, value: object) -> str:
    return (
        '<div class="section">'
        f'<div class="section-title">{escape(title)}</div>'
        f'<div class="text-block">{_structured_multiline(value)}</div>'
        "</div>"
    )


def _positive_number_or_dash(value: object) -> str:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return "-"
    return str(number) if number > 0 else "-"
