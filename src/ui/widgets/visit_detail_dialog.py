from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from ui.popup_i18n import localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import apply_clickable_affordance

logger = logging.getLogger(__name__)


class VisitDetailDialog(QDialog):
    """Visit-detail popup — fully styled by ui/theme.py via objectName + role props."""

    def __init__(self, visit: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VisitDetailDialog")
        self.setWindowTitle(localize_popup_message("Visit detail"))
        self.setMinimumWidth(500)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._build_ui(visit)
        fit_dialog_to_available_screen(self, preferred_width=640)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self, v: dict) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        body_scroll = QScrollArea()
        body_scroll.setObjectName("VisitDetailBodyScroll")
        body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        body_scroll.setWidget(self._build_body(v))
        root.addWidget(body_scroll, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("VisitDetailHeader")
        header.setFixedHeight(52)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0)

        lay.addStretch()
        return header

    def _build_body(self, v: dict) -> QFrame:
        body = QFrame()
        body.setObjectName("VisitDetailBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 10)
        lay.setSpacing(10)

        lay.addWidget(self._build_basic_info(v))
        lay.addWidget(self._build_tech_section(v))

        summary = (v.get("summary") or "").strip()
        if summary:
            lay.addWidget(self._build_summary_section(summary))
        if v.get("defect_notes") or v.get("product_sections"):
            lay.addWidget(self._build_defect_note_section(v))

        return body

    def _build_basic_info(self, v: dict) -> QFrame:
        """2×2 grid: date / supplier / work-order / production qty."""
        frame = self._card_frame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(2)

        work_order = (v.get("work_order_no") or "").strip() or "—"
        fields = [
            ("日期",    str(v.get("visit_date") or "—")),
            ("供應商",  str(v.get("supplier_name") or "—")),
            ("工單",    work_order),
            ("數量",    str(v.get("production_qty") or "0")),
        ]
        for i, (lbl_text, val_text) in enumerate(fields):
            row, col = divmod(i, 2)
            grid.addWidget(self._meta_label(lbl_text), row * 2,     col * 3)
            grid.addWidget(self._value_label(val_text), row * 2 + 1, col * 3)
            if col == 0:
                sep = QFrame()
                sep.setProperty("role", "separator")
                sep.setFixedWidth(1)
                grid.addWidget(sep, row * 2, 1, 2, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)
        return frame

    def _build_tech_section(self, v: dict) -> QFrame:
        frame = self._card_frame()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._meta_label("技轉狀態"))
        transferred = bool(v.get("tech_transfer", False))
        top_row.addWidget(self._status_badge("已技轉" if transferred else "未技轉", transferred))
        top_row.addStretch()
        lay.addLayout(top_row)

        rule = QFrame()
        rule.setProperty("role", "separator")
        rule.setFixedHeight(1)
        lay.addWidget(rule)

        items_grid = QGridLayout()
        items_grid.setHorizontalSpacing(12)
        items_grid.setVerticalSpacing(4)
        items = [
            ("作業標準書",    "tech_transfer_doc"),
            ("載具要求",      "carrier_requirement"),
            ("Underfill 要求", "dispensing_process"),
            ("電訊測試",      "functional_test"),
            ("包裝規範",      "packaging_requirement"),
        ]
        for i, (label, key) in enumerate(items):
            row, col = divmod(i, 2)
            has_it = bool(v.get(key, False))
            items_grid.addWidget(self._item_row(label, has_it), row, col)
        items_grid.setColumnStretch(0, 1)
        items_grid.setColumnStretch(1, 1)
        lay.addLayout(items_grid)
        return frame

    def _build_summary_section(self, summary: str) -> QFrame:
        frame = self._card_frame()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(4)
        lay.addWidget(self._meta_label("摘要"))

        text = QLabel(summary)
        text.setWordWrap(True)
        text.setProperty("role", "summary")
        lay.addWidget(text)
        return frame

    def _build_defect_note_section(self, visit: dict) -> QFrame:
        frame = self._card_frame()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(8)
        lay.addWidget(self._meta_label("缺失 / 改善紀錄"))

        visit_level = [
            item
            for item in list(visit.get("defect_notes") or [])
            if not str(item.get("visit_product_section_id") or "").strip()
        ]
        if visit_level:
            lay.addWidget(self._value_label("訪廠層級"))
            for note in visit_level:
                lay.addWidget(self._defect_note_label(note))

        for section in list(visit.get("product_sections") or []):
            notes = list(section.get("defect_notes") or [])
            if not notes:
                continue
            product_name = str(section.get("product_name") or "未指定產品").strip()
            lay.addWidget(self._value_label(product_name))
            for note in notes:
                lay.addWidget(self._defect_note_label(note))

        return frame

    def _defect_note_label(self, note: dict) -> QLabel:
        defect = str(note.get("defect_desc") or "").strip() or "-"
        improvement = str(note.get("improvement_desc") or "").strip() or "待補改善"
        remark = str(note.get("note") or "").strip()
        text = f"缺失：{defect}\n改善：{improvement}"
        if remark:
            text += f"\n備註：{remark}"
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("role", "summary")
        return label

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("VisitDetailFooter")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(16, 10, 16, 14)
        lay.addStretch()

        close_btn = QPushButton("關閉")
        close_btn.setMinimumWidth(88)
        close_btn.setProperty("role", "visitDetailClose")
        apply_clickable_affordance(close_btn, tooltip="關閉訪廠明細")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
        return footer

    # ── Widget helpers ─────────────────────────────────────────────────────

    def _card_frame(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("role", "visitDetailCard")
        return frame

    def _meta_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "meta")
        return lbl

    def _value_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setProperty("role", "value")
        return lbl

    def _status_badge(self, text: str, is_positive: bool) -> QLabel:
        badge = QLabel(f"  {text}  ")
        badge.setProperty("role", "statusBadge")
        badge.setProperty("tone", "success" if is_positive else "pending")
        return badge

    def _item_row(self, label: str, has_it: bool) -> QFrame:
        row = QFrame()
        row.setObjectName("vdItemRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 3, 8, 3)
        lay.setSpacing(6)

        dot = QLabel("✓" if has_it else "–")
        dot.setFixedWidth(16)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setProperty("role", "techDot")
        if has_it:
            dot.setProperty("state", "on")

        name = QLabel(label)
        name.setProperty("role", "techName")
        if has_it:
            name.setProperty("state", "on")

        val = QLabel("有" if has_it else "沒有")
        val.setProperty("role", "techValue")
        if has_it:
            val.setProperty("state", "on")

        lay.addWidget(dot)
        lay.addWidget(name, stretch=1)
        lay.addWidget(val)
        return row
