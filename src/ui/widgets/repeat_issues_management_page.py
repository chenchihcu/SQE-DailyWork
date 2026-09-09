"""專屬潛在重複異常查詢、檢閱與管理頁面。"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import repeat_issue_service
from services.event import _anomaly_service, _anomaly_workbench_service
from services.event._supplier_service import list_active_suppliers
from ui.layout_constants import (
    CONTROL_MIN_HEIGHT,
    CONTROL_ROW_SPACING,
    FORM_HORIZONTAL_SPACING,
    PAGE_OUTER_MARGINS,
    PANEL_MARGINS,
)
from ui.widgets.common_widgets import (
    EmptyStateWidget,
    create_section_card,
    make_multiline_label,
    style_table,
    sync_multiline_label_geometry,
)

logger = logging.getLogger(__name__)


class RepeatIssuesManagementPage(QWidget):
    """潛在重複異常專屬查詢、檢閱與處置管理頁面。"""

    open_anomaly_requested = Signal(str)

    def __init__(self, main_window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._source_anomaly_id: str = ""
        self._source_detail: dict[str, Any] = {}
        self._source_root_cause: dict[str, Any] | None = None
        self._selected_peer_id: str = ""
        self._selected_peer_detail: dict[str, Any] = {}
        self._selected_peer_root_cause: dict[str, Any] | None = None
        self._current_rows: list[dict[str, Any]] = []

        self.setObjectName("RepeatIssuesManagementPage")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(CONTROL_ROW_SPACING)

        # 頂部標題與返回列
        header = QFrame()
        header.setObjectName("RepeatIssuesHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel("潛在重複異常管理")
        self.title_label.setProperty("role", "title")
        self.subtitle_label = QLabel("比對同供應商歷史相似案件與重複判定")
        self.subtitle_label.setProperty("role", "muted")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        header_layout.addLayout(title_box, 1)

        self.back_button = QPushButton("返回上一頁")
        self.back_button.setProperty("variant", "secondary")
        self.back_button.clicked.connect(self._on_back_clicked)
        header_layout.addWidget(self.back_button)
        root.addWidget(header)

        # 查詢與過濾工具列
        filter_card = QFrame(self)
        filter_card.setProperty("role", "panel")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(*PANEL_MARGINS)
        filter_layout.setSpacing(FORM_HORIZONTAL_SPACING)

        filter_layout.addWidget(QLabel("供應商："))
        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(160)
        self.supplier_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.supplier_combo)

        filter_layout.addWidget(QLabel("相似度門檻："))
        self.min_score_combo = QComboBox()
        self.min_score_combo.addItems(["全部 (>=0)", ">= 50 分", ">= 60 分", ">= 70 分", ">= 80 分"])
        self.min_score_combo.setCurrentIndex(2)
        self.min_score_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.min_score_combo)

        filter_layout.addWidget(QLabel("判定狀態："))
        self.disposition_combo = QComboBox()
        self.disposition_combo.addItems(["全部", "待確認", "已確認重複", "已排除"])
        self.disposition_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.disposition_combo)

        filter_layout.addWidget(QLabel("單號搜尋："))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("輸入異常單號...")
        self.search_input.returnPressed.connect(self._on_filter_changed)
        filter_layout.addWidget(self.search_input)

        self.refresh_button = QPushButton("重新整理")
        self.refresh_button.setProperty("variant", "secondary")
        self.refresh_button.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.refresh_button)

        self.reset_filter_button = QPushButton("重置條件")
        self.reset_filter_button.setProperty("variant", "secondary")
        self.reset_filter_button.clicked.connect(self._on_reset_filters)
        filter_layout.addWidget(self.reset_filter_button)

        root.addWidget(filter_card)

        # 上下分割區域
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setObjectName("RepeatIssuesSplitter")

        # 上部：相似案件表格清單
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        list_header_layout = QHBoxLayout()
        self.list_count_label = QLabel("潛在重複案件清單 (0 件)")
        self.list_count_label.setProperty("role", "sectionTitle")
        list_header_layout.addWidget(self.list_count_label)
        list_header_layout.addStretch(1)
        table_layout.addLayout(list_header_layout)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ("來源單號", "歷史單號", "異常日期", "供應商", "品名 / 料號", "相似度", "判定狀態", "歷史案件狀態")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        style_table(self.table)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        table_layout.addWidget(self.table)

        self.empty_state = EmptyStateWidget("無符合條件的潛在重複異常案件")
        self.empty_state.hide()
        table_layout.addWidget(self.empty_state)

        splitter.addWidget(table_container)

        # 下部：雙案對照面板與處置操作列
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(CONTROL_ROW_SPACING)

        compare_title_row = QHBoxLayout()
        compare_title = QLabel("雙案詳細對照與重複判定處置")
        compare_title.setProperty("role", "sectionTitle")
        compare_title_row.addWidget(compare_title)
        compare_title_row.addStretch(1)
        bottom_layout.addLayout(compare_title_row)

        compare_cards_layout = QHBoxLayout()
        compare_cards_layout.setSpacing(FORM_HORIZONTAL_SPACING)

        # 左欄：基準案件
        self.source_card = create_section_card(self)
        self.source_card.setObjectName("ComparisonSourceCard")
        sc_layout = self.source_card.layout()
        assert sc_layout is not None
        sc_layout.setSpacing(6)

        self.sc_header = QLabel("【基準案件】")
        self.sc_header.setProperty("role", "sectionTitle")
        sc_layout.addWidget(self.sc_header)

        self.sc_meta_summary = make_multiline_label("—", role="helperText")
        sc_layout.addWidget(self.sc_meta_summary)

        self.sc_meta_product = make_multiline_label("—", role="helperText")
        sc_layout.addWidget(self.sc_meta_product)

        sc_layout.addWidget(QLabel("不良現象："))
        self.sc_problem = make_multiline_label("—")
        self.sc_problem.setStyleSheet("background: rgba(0,0,0,0.03); border-radius: 4px; padding: 6px;")
        sc_layout.addWidget(self.sc_problem)

        sc_layout.addWidget(QLabel("根本原因："))
        self.sc_root_cause = make_multiline_label("—")
        self.sc_root_cause.setStyleSheet("background: rgba(0,0,0,0.03); border-radius: 4px; padding: 6px;")
        sc_layout.addWidget(self.sc_root_cause)

        sc_layout.addWidget(QLabel("改善措施 / 對策："))
        self.sc_actions = make_multiline_label("—")
        self.sc_actions.setStyleSheet("background: rgba(0,0,0,0.03); border-radius: 4px; padding: 6px;")
        sc_layout.addWidget(self.sc_actions)

        compare_cards_layout.addWidget(self.source_card, 1)

        # 右欄：歷史相似案件
        self.peer_card = create_section_card(self)
        self.peer_card.setObjectName("ComparisonPeerCard")
        pc_layout = self.peer_card.layout()
        assert pc_layout is not None
        pc_layout.setSpacing(6)

        self.pc_header = QLabel("【歷史相似案件】")
        self.pc_header.setProperty("role", "sectionTitle")
        pc_layout.addWidget(self.pc_header)

        self.pc_meta_summary = make_multiline_label("—", role="helperText")
        pc_layout.addWidget(self.pc_meta_summary)

        self.pc_meta_product = make_multiline_label("—", role="helperText")
        pc_layout.addWidget(self.pc_meta_product)

        self.pc_meta_reasons = make_multiline_label("—", role="helperText")
        pc_layout.addWidget(self.pc_meta_reasons)

        pc_layout.addWidget(QLabel("不良現象："))
        self.pc_problem = make_multiline_label("—")
        self.pc_problem.setStyleSheet("background: rgba(0,0,0,0.03); border-radius: 4px; padding: 6px;")
        pc_layout.addWidget(self.pc_problem)

        pc_layout.addWidget(QLabel("根本原因："))
        self.pc_root_cause = make_multiline_label("—")
        self.pc_root_cause.setStyleSheet("background: rgba(0,0,0,0.03); border-radius: 4px; padding: 6px;")
        pc_layout.addWidget(self.pc_root_cause)

        pc_layout.addWidget(QLabel("改善措施 / 對策："))
        self.pc_actions = make_multiline_label("—")
        self.pc_actions.setStyleSheet("background: rgba(0,0,0,0.03); border-radius: 4px; padding: 6px;")
        pc_layout.addWidget(self.pc_actions)

        compare_cards_layout.addWidget(self.peer_card, 1)
        bottom_layout.addLayout(compare_cards_layout, 1)

        # 處置動作操作列
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.confirm_btn = QPushButton("✔ 確認為重複發生")
        self.confirm_btn.setProperty("variant", "primary")
        self.confirm_btn.clicked.connect(self._mark_confirmed)
        action_bar.addWidget(self.confirm_btn)

        self.dismiss_btn = QPushButton("✖ 排除 / 忽略")
        self.dismiss_btn.setProperty("variant", "secondary")
        self.dismiss_btn.clicked.connect(self._mark_dismissed)
        action_bar.addWidget(self.dismiss_btn)

        self.reset_disp_btn = QPushButton("重置為待確認")
        self.reset_disp_btn.setProperty("variant", "secondary")
        self.reset_disp_btn.clicked.connect(self._mark_pending)
        action_bar.addWidget(self.reset_disp_btn)

        action_bar.addSpacing(20)

        self.open_peer_btn = QPushButton("查看歷史案件 8D 詳情")
        self.open_peer_btn.setProperty("variant", "secondary")
        self.open_peer_btn.clicked.connect(self._open_peer_detail)
        action_bar.addWidget(self.open_peer_btn)

        self.open_source_btn = QPushButton("前往基準案件 8D 詳情")
        self.open_source_btn.setProperty("variant", "secondary")
        self.open_source_btn.clicked.connect(self._open_source_detail)
        action_bar.addWidget(self.open_source_btn)

        action_bar.addStretch(1)
        bottom_layout.addLayout(action_bar)

        splitter.addWidget(bottom_container)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, 1)

        self._populate_suppliers_filter()
        self._clear_comparison()

    def _populate_suppliers_filter(self) -> None:
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("全部供應商", "")
        try:
            suppliers = list_active_suppliers()
            for s in suppliers:
                sid = str(s.get("id") or "")
                name = str(s.get("name") or "")
                if name:
                    self.supplier_combo.addItem(name, sid)
        except Exception as exc:
            logger.warning("載入供應商清單失敗: %s", exc)
        self.supplier_combo.blockSignals(False)

    def load_case(
        self,
        anomaly_id: str | None = None,
        supplier_id: str | None = None,
    ) -> None:
        self._source_anomaly_id = str(anomaly_id or "").strip()
        self._selected_peer_id = ""

        if self._source_anomaly_id:
            try:
                self._source_detail = _anomaly_service.get_anomaly_detail(self._source_anomaly_id)
                self._source_root_cause = _anomaly_workbench_service.get_root_cause(self._source_anomaly_id)
            except Exception as exc:
                logger.warning("取得基準案件詳情失敗: %s", exc)
                self._source_detail = {}
                self._source_root_cause = None

            s_no = self._source_detail.get("anomaly_no") or self._source_anomaly_id
            self.back_button.setText(f"返回案件 {s_no}")

            sid = str(self._source_detail.get("supplier_id") or "")
            if sid:
                idx = self.supplier_combo.findData(sid)
                if idx >= 0:
                    self.supplier_combo.blockSignals(True)
                    self.supplier_combo.setCurrentIndex(idx)
                    self.supplier_combo.blockSignals(False)
        else:
            self._source_detail = {}
            self._source_root_cause = None
            self.back_button.setText("返回上一頁")
            if supplier_id:
                idx = self.supplier_combo.findData(str(supplier_id).strip())
                if idx >= 0:
                    self.supplier_combo.blockSignals(True)
                    self.supplier_combo.setCurrentIndex(idx)
                    self.supplier_combo.blockSignals(False)

        self.refresh_data()

    def refresh_data(self) -> None:
        min_score = 0
        score_text = self.min_score_combo.currentText()
        if "50" in score_text:
            min_score = 50
        elif "60" in score_text:
            min_score = 60
        elif "70" in score_text:
            min_score = 70
        elif "80" in score_text:
            min_score = 80

        disp_filter = self.disposition_combo.currentText()
        if disp_filter == "全部":
            disp_filter = ""

        supplier_id = str(self.supplier_combo.currentData() or "")
        search_kw = self.search_input.text().strip().lower()

        try:
            if self._source_anomaly_id:
                raw_rows = repeat_issue_service.list_repeat_issues(self._source_anomaly_id)
                rows = []
                for r in raw_rows:
                    item = dict(r)
                    item["anomaly_id"] = self._source_anomaly_id
                    item["source_anomaly_no"] = self._source_detail.get("anomaly_no", "")
                    item["source_anomaly_date"] = self._source_detail.get("anomaly_date", "")
                    item["supplier_name"] = self._source_detail.get("supplier_name", "")
                    item["source_product_name"] = self._source_detail.get("product_name", "")
                    item["source_category"] = self._source_detail.get("category", "")
                    item["source_status"] = self._source_detail.get("status", "")
                    item["source_problem_desc"] = self._source_detail.get("problem_desc", "")

                    score = int(item.get("similarity_score") or 0)
                    disp = str(item.get("disposition") or "")
                    if min_score > 0 and score < min_score:
                        continue
                    if disp_filter and disp != disp_filter:
                        continue
                    if search_kw:
                        target = f"{item.get('anomaly_no', '')} {item.get('product_name', '')}".lower()
                        if search_kw not in target:
                            continue
                    rows.append(item)
            else:
                rows = repeat_issue_service.query_all_repeat_issues(
                    supplier_id=supplier_id,
                    min_score=min_score,
                    disposition=disp_filter,
                )
                if search_kw:
                    filtered = []
                    for r in rows:
                        target = f"{r.get('source_anomaly_no', '')} {r.get('anomaly_no', '')} {r.get('product_name', '')}".lower()
                        if search_kw in target:
                            filtered.append(r)
                    rows = filtered
        except Exception as exc:
            logger.warning("查詢重複案件失敗: %s", exc)
            rows = []

        self._current_rows = rows
        self._render_table(rows)

    def _render_table(self, rows: list[dict[str, Any]]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        has_rows = bool(rows)
        self.table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        self.list_count_label.setText(f"潛在重複案件清單 ({len(rows)} 件)")

        for index, row in enumerate(rows):
            self.table.insertRow(index)
            src_no = row.get("source_anomaly_no") or "—"
            peer_no = row.get("anomaly_no") or "—"
            date = row.get("anomaly_date") or "—"
            supplier = row.get("supplier_name") or "—"
            product = row.get("product_name") or "—"
            score = str(row.get("similarity_score") or "0")
            disp = row.get("disposition") or repeat_issue_service.DISPOSITION_PENDING
            status = row.get("status") or "—"

            values = (src_no, peer_no, date, supplier, product, score, disp, status)
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col == 1:
                    item.setData(Qt.ItemDataRole.UserRole, row.get("peer_anomaly_id"))
                    item.setData(Qt.ItemDataRole.UserRole + 1, row.get("anomaly_id"))
                if col == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if disp == repeat_issue_service.DISPOSITION_CONFIRMED:
                        item.setForeground(Qt.GlobalColor.darkRed)
                    elif disp == repeat_issue_service.DISPOSITION_DISMISSED:
                        item.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(index, col, item)

        self.table.blockSignals(False)

        if has_rows:
            self.table.selectRow(0)
            self._update_comparison_for_row(0)
        else:
            self._clear_comparison()

    def _on_table_selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            self._clear_comparison()
            return
        row = selected[0].row()
        self._update_comparison_for_row(row)

    def _update_comparison_for_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._current_rows):
            self._clear_comparison()
            return
        data = self._current_rows[row_index]
        source_id = str(data.get("anomaly_id") or "").strip()
        peer_id = str(data.get("peer_anomaly_id") or "").strip()
        self._selected_peer_id = peer_id

        src_detail = self._source_detail if source_id == self._source_anomaly_id and self._source_detail else {}
        if not src_detail and source_id:
            try:
                src_detail = _anomaly_service.get_anomaly_detail(source_id)
            except Exception:
                src_detail = {}

        src_rc = self._source_root_cause if source_id == self._source_anomaly_id else None
        if src_rc is None and source_id:
            try:
                src_rc = _anomaly_workbench_service.get_root_cause(source_id)
            except Exception:
                src_rc = None

        try:
            peer_detail = _anomaly_service.get_anomaly_detail(peer_id)
        except Exception:
            peer_detail = {}
        try:
            peer_rc = _anomaly_workbench_service.get_root_cause(peer_id)
        except Exception:
            peer_rc = None

        self._selected_peer_detail = peer_detail
        self._selected_peer_root_cause = peer_rc

        s_no = src_detail.get("anomaly_no") or source_id or "—"
        s_status = src_detail.get("status") or "—"
        s_supplier = src_detail.get("supplier_name") or "—"
        s_cat = src_detail.get("category") or "—"
        s_date = src_detail.get("anomaly_date") or "—"
        s_product = src_detail.get("product_name") or "—"
        s_code = src_detail.get("product_code") or ""
        s_prob = src_detail.get("problem_desc") or "—"
        s_rc_text = (src_rc.get("statement") or "（尚未建立根本原因分析）") if src_rc else "（尚未建立根本原因分析）"
        s_act = src_detail.get("improvement_desc") or "—"

        self.sc_header.setText(f"【基準案件】{s_no}  [{s_status}]")
        self.sc_meta_summary.setText(
            f"供應商：{s_supplier}　|　類別：{s_cat}　|　日期：{s_date}"
        )
        self.sc_meta_product.setText(f"料號品名：{s_code} {s_product}".strip())
        sync_multiline_label_geometry(self.sc_meta_summary)
        sync_multiline_label_geometry(self.sc_meta_product)
        self.sc_problem.setText(s_prob)
        self.sc_root_cause.setText(s_rc_text)
        self.sc_actions.setText(s_act)
        sync_multiline_label_geometry(self.sc_problem)
        sync_multiline_label_geometry(self.sc_root_cause)
        sync_multiline_label_geometry(self.sc_actions)

        p_no = peer_detail.get("anomaly_no") or peer_id or "—"
        p_status = peer_detail.get("status") or "—"
        p_supplier = peer_detail.get("supplier_name") or "—"
        p_cat = peer_detail.get("category") or "—"
        p_date = peer_detail.get("anomaly_date") or "—"
        p_product = peer_detail.get("product_name") or "—"
        p_code = peer_detail.get("product_code") or ""
        p_prob = peer_detail.get("problem_desc") or "—"
        p_rc_text = (peer_rc.get("statement") or "（尚未建立根本原因分析）") if peer_rc else "（尚未建立根本原因分析）"
        p_act = peer_detail.get("improvement_desc") or "—"
        score = data.get("similarity_score") or "0"
        reasons = str(data.get("match_reasons") or "").replace("\n", "；")
        disp = data.get("disposition") or repeat_issue_service.DISPOSITION_PENDING

        self.pc_header.setText(f"【歷史案件】{p_no}  [{p_status}]  相似度：{score} 分 ({disp})")
        self.pc_meta_summary.setText(
            f"供應商：{p_supplier}　|　類別：{p_cat}　|　日期：{p_date}"
        )
        self.pc_meta_product.setText(f"料號品名：{p_code} {p_product}".strip())
        self.pc_meta_reasons.setText(f"比對特徵：{reasons}")
        sync_multiline_label_geometry(self.pc_meta_summary)
        sync_multiline_label_geometry(self.pc_meta_product)
        sync_multiline_label_geometry(self.pc_meta_reasons)
        self.pc_problem.setText(p_prob)
        self.pc_root_cause.setText(p_rc_text)
        self.pc_actions.setText(p_act)
        sync_multiline_label_geometry(self.pc_problem)
        sync_multiline_label_geometry(self.pc_root_cause)
        sync_multiline_label_geometry(self.pc_actions)

        self.confirm_btn.setEnabled(bool(source_id and peer_id))
        self.dismiss_btn.setEnabled(bool(source_id and peer_id))
        self.reset_disp_btn.setEnabled(bool(source_id and peer_id))
        self.open_peer_btn.setEnabled(bool(peer_id))
        self.open_source_btn.setEnabled(bool(source_id))

    def _clear_comparison(self) -> None:
        self.sc_header.setText("【基準案件】")
        self.sc_meta_summary.setText("—")
        self.sc_meta_product.setText("—")
        self.sc_problem.setText("—")
        self.sc_root_cause.setText("—")
        self.sc_actions.setText("—")

        self.pc_header.setText("【歷史相似案件】")
        self.pc_meta_summary.setText("—")
        self.pc_meta_product.setText("—")
        self.pc_meta_reasons.setText("—")
        self.pc_problem.setText("—")
        self.pc_root_cause.setText("—")
        self.pc_actions.setText("—")

        self.confirm_btn.setEnabled(False)
        self.dismiss_btn.setEnabled(False)
        self.reset_disp_btn.setEnabled(False)
        self.open_peer_btn.setEnabled(False)
        self.open_source_btn.setEnabled(False)

    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._current_rows):
            return
        peer_id = self._current_rows[row].get("peer_anomaly_id")
        if peer_id:
            self._open_peer_detail()

    def _update_disposition(self, disposition: str) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._current_rows):
            return
        data = self._current_rows[row]
        source_id = str(data.get("anomaly_id") or "")
        peer_id = str(data.get("peer_anomaly_id") or "")
        if not source_id or not peer_id:
            return

        repeat_issue_service.set_repeat_link_disposition(source_id, peer_id, disposition)
        data["disposition"] = disposition

        disp_item = self.table.item(row, 6)
        if disp_item:
            disp_item.setText(disposition)
            if disposition == repeat_issue_service.DISPOSITION_CONFIRMED:
                disp_item.setForeground(Qt.GlobalColor.darkRed)
            elif disposition == repeat_issue_service.DISPOSITION_DISMISSED:
                disp_item.setForeground(Qt.GlobalColor.gray)
            else:
                disp_item.setForeground(Qt.GlobalColor.black)

        self._update_comparison_for_row(row)

    def _mark_confirmed(self) -> None:
        self._update_disposition(repeat_issue_service.DISPOSITION_CONFIRMED)

    def _mark_dismissed(self) -> None:
        self._update_disposition(repeat_issue_service.DISPOSITION_DISMISSED)

    def _mark_pending(self) -> None:
        self._update_disposition(repeat_issue_service.DISPOSITION_PENDING)

    def _open_peer_detail(self) -> None:
        if self._selected_peer_id and hasattr(self.main_window, "open_anomaly_management"):
            self.main_window.open_anomaly_management(self._selected_peer_id)

    def _open_source_detail(self) -> None:
        row = self.table.currentRow()
        source_id = self._source_anomaly_id
        if row >= 0 and row < len(self._current_rows):
            source_id = self._current_rows[row].get("anomaly_id") or source_id
        if source_id and hasattr(self.main_window, "open_anomaly_management"):
            self.main_window.open_anomaly_management(source_id)

    def _on_back_clicked(self) -> None:
        if self._source_anomaly_id and hasattr(self.main_window, "open_anomaly_management"):
            self.main_window.open_anomaly_management(self._source_anomaly_id)
        elif hasattr(self.main_window, "return_to_event_list"):
            self.main_window.return_to_event_list()

    def _on_filter_changed(self) -> None:
        self.refresh_data()

    def _on_reset_filters(self) -> None:
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.setCurrentIndex(0)
        self.supplier_combo.blockSignals(False)

        self.min_score_combo.blockSignals(True)
        self.min_score_combo.setCurrentIndex(2)
        self.min_score_combo.blockSignals(False)

        self.disposition_combo.blockSignals(True)
        self.disposition_combo.setCurrentIndex(0)
        self.disposition_combo.blockSignals(False)

        self.search_input.clear()
        self.refresh_data()