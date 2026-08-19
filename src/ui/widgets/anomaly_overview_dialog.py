"""Anomaly case-workbench overview dialog.

Phase "異常案件工作台 UI 對接" first increment: a read-only overview of one
anomaly that surfaces the actionable case-workbench read model — current next
action, overdue, analysis notes, root cause, corrective actions, attachments,
Supplier 8D reviews and the audit/timeline feed. It is intentionally read-only
so it does not re-implement write paths or dirty guards; editing stays in the
existing NewAnomalyDialog / CloseAnomalyDialog flows.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.layout_constants import (
    CONTROL_ROW_SPACING,
    DIALOG_BODY_MARGINS,
    DIALOG_FOOTER_CLOSE_MIN_WIDTH,
    DIALOG_HEADER_FOOTER_H_MARGIN,
    DIALOG_HEADER_HEIGHT,
    WORKBENCH_DIALOG_MIN_HEIGHT,
    WORKBENCH_DIALOG_MIN_WIDTH,
    WORKBENCH_DIALOG_PREFERRED_WIDTH,
)
from ui.popup_i18n import localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    apply_clickable_affordance,
    create_section_card,
)
from services.event import (
    _anomaly_action_service,
    _anomaly_service,
    _anomaly_workbench_service,
)


class AnomalyOverviewDialog(QDialog):
    """Read-only case-workbench summary for a single anomaly."""

    def __init__(self, anomaly_id: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AnomalyOverviewDialog")
        self.setModal(True)
        self.setWindowTitle(localize_popup_message("異常案件工作台概況"))
        self._anomaly_id = anomaly_id.strip()
        self.setMinimumSize(WORKBENCH_DIALOG_MIN_WIDTH, WORKBENCH_DIALOG_MIN_HEIGHT)

        detail = _anomaly_service.get_anomaly_detail(self._anomaly_id)
        self._detail = detail
        self._overview = _anomaly_workbench_service.get_overview_card(
            self._anomaly_id
        )
        self._build_ui()
        fit_dialog_to_available_screen(
            self, preferred_width=WORKBENCH_DIALOG_PREFERRED_WIDTH
        )

    # ── construction ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        body = QScrollArea()
        body.setObjectName("AnomalyOverviewBodyScroll")
        body.setWidgetResizable(True)
        body.setFrameShape(QFrame.Shape.NoFrame)
        body.setWidget(self._build_body())
        root.addWidget(body, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("AnomalyOverviewHeader")
        header.setFixedHeight(DIALOG_HEADER_HEIGHT)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(
            DIALOG_HEADER_FOOTER_H_MARGIN, 0, DIALOG_HEADER_FOOTER_H_MARGIN, 0
        )
        no = str(self._detail.get("anomaly_no") or self._anomaly_id)
        supplier = str(self._detail.get("supplier_name") or "")
        status = str(self._detail.get("status") or "")
        title = QLabel(f"異常案件 {no} — {supplier} [{status}]")
        title.setProperty("role", "title")
        lay.addWidget(title)
        lay.addStretch()
        return header

    def _build_body(self) -> QFrame:
        body = QFrame()
        body.setObjectName("AnomalyOverviewBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(*DIALOG_BODY_MARGINS)
        lay.setSpacing(CONTROL_ROW_SPACING)

        lay.addWidget(self._build_next_action_card())
        lay.addWidget(self._build_root_cause_card())
        lay.addWidget(self._build_notes_card())
        lay.addWidget(self._build_corrective_actions_card())
        lay.addWidget(self._build_8d_card())
        lay.addWidget(self._build_attachments_card())
        lay.addWidget(self._build_timeline_card())
        return body

    def _build_next_action_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("目前處置與逾期"))
        overview = self._overview
        overdue = "是" if overview.get("overdue") else "否"
        actions = _anomaly_action_service.list_actions(self._anomaly_id)
        open_actions = [a for a in actions if a.get("status") == "進行中"]
        closed_actions = [a for a in actions if a.get("status") != "進行中"]
        current = overview.get("current_action") or {}
        if current:
            desc = str(current.get("description") or "—")
            owner = str(current.get("owner") or "—")
            due = str(current.get("due_date") or "—")
            lay.addWidget(self._kv("目前處置", desc))
            lay.addWidget(self._kv("負責人", owner))
            lay.addWidget(self._kv("到期日", due))
        else:
            # Historical fallback from the anomaly table (not duplicated per-UI).
            pending = str(self._detail.get("pending_items") or "")
            resp = str(self._detail.get("responsible_person") or "")
            due = str(self._detail.get("due_date") or "")
            if pending or resp or due:
                lay.addWidget(self._kv("目前處置（歷史）", pending or "—"))
                lay.addWidget(self._kv("負責人", resp or "—"))
                lay.addWidget(self._kv("到期日", due or "—"))
            else:
                lay.addWidget(EmptyStateWidgetWrapper("尚無處置紀錄"))
        lay.addWidget(self._kv("進行中處置數", str(overview.get("open_action_count", 0))))
        lay.addWidget(self._kv("逾期", overdue))

        if open_actions:
            lay.addWidget(self._section_title("進行中處置"))
            for action in open_actions:
                lay.addWidget(self._build_action_row(action))
        if closed_actions:
            lay.addWidget(self._section_title("已完成 / 已取消處置"))
            for action in closed_actions:
                lay.addWidget(self._build_action_row(action, show_update=False))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(CONTROL_ROW_SPACING)
        btn_add = QPushButton("新增處置")
        btn_add.setAccessibleName("新增處置")
        apply_clickable_affordance(btn_add, tooltip="建立一筆新的處置")
        btn_add.clicked.connect(self._open_add_action_dialog)
        btn_row.addWidget(btn_add)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return card

    def _build_action_row(
        self, action: dict, *, show_update: bool = True
    ) -> QWidget:
        desc = str(action.get("description") or "—")
        status = str(action.get("status") or "—")
        owner = str(action.get("owner") or "—")
        due = str(action.get("due_date") or "—")
        wrapper = QFrame()
        wrapper.setObjectName("AnomalyActionRow")
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(CONTROL_ROW_SPACING)
        v.addWidget(self._kv(f"{desc}（{status}）", f"負責人：{owner}　到期：{due}"))
        if show_update:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(CONTROL_ROW_SPACING)
            btn = QPushButton("更新狀態")
            btn.setAccessibleName(f"更新處置狀態：{desc[:24]}")
            apply_clickable_affordance(
                btn, tooltip="將此處置標記為已完成或已取消"
            )
            btn.clicked.connect(
                lambda _checked=False, aid=action.get("id"), summary=desc: self._open_complete_action_dialog(
                    aid, summary
                )
            )
            btn_row.addWidget(btn)
            btn_row.addStretch(1)
            v.addLayout(btn_row)
        return wrapper

    def _open_add_action_dialog(self) -> None:
        from ui.widgets.anomaly_action_dialog import AddAnomalyActionDialog
        dialog = AddAnomalyActionDialog(self._anomaly_id, self)
        dialog.action_created.connect(lambda _id: self._refresh())
        dialog.exec()

    def _open_complete_action_dialog(
        self, action_id: str, action_summary: str
    ) -> None:
        from ui.widgets.complete_action_dialog import CompleteActionDialog
        dialog = CompleteActionDialog(
            action_id, action_summary=action_summary, parent=self
        )
        dialog.action_updated.connect(lambda _id: self._refresh())
        dialog.exec()

    def _refresh(self) -> None:
        self._overview = _anomaly_workbench_service.get_overview_card(
            self._anomaly_id
        )
        # Rebuild the scroll body content by re-running the body builder.
        # (Simplest: replace the body widget.)
        body_scroll = self.findChild(QScrollArea, "AnomalyOverviewBodyScroll")
        if body_scroll is not None:
            old = body_scroll.takeWidget()
            if old is not None:
                old.setParent(None)
                old.deleteLater()
            body_scroll.setWidget(self._build_body())

    def _build_root_cause_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("根本原因"))
        rc = _anomaly_workbench_service.get_root_cause(self._anomaly_id)
        if not rc or rc.get("status") in (None, "", "尚未開始"):
            lay.addWidget(EmptyStateWidgetWrapper("尚未建立根本原因"))
            return card
        lay.addWidget(self._kv("狀態", str(rc.get("status") or "—")))
        lay.addWidget(self._kv("說明", str(rc.get("statement") or "—")))
        if rc.get("validation_method"):
            lay.addWidget(self._kv("驗證方式", str(rc.get("validation_method"))))
        return card

    def _build_notes_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("分析紀錄"))
        notes = _anomaly_workbench_service.list_analysis_notes(self._anomaly_id)
        if not notes:
            lay.addWidget(EmptyStateWidgetWrapper("尚無分析紀錄"))
        else:
            for note in notes:
                label = str(note.get("evidence_label") or note.get("evidence_type") or "")
                author = str(note.get("author_name") or "未知")
                content = str(note.get("content") or "")
                row = QLabel(f"[{label}] {author}")
                row.setProperty("role", "meta")
                lay.addWidget(row)
                body_lbl = QLabel(content)
                body_lbl.setWordWrap(True)
                body_lbl.setProperty("role", "summary")
                lay.addWidget(body_lbl)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(CONTROL_ROW_SPACING)
        btn_add = QPushButton("新增分析紀錄")
        apply_clickable_affordance(btn_add, tooltip="建立一筆分析紀錄")
        btn_add.clicked.connect(self._open_add_note_dialog)
        btn_row.addWidget(btn_add)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return card

    def _open_add_note_dialog(self) -> None:
        from ui.widgets.anomaly_note_dialog import AnomalyNoteDialog
        dialog = AnomalyNoteDialog(self._anomaly_id, self)
        dialog.note_created.connect(lambda _id: self._refresh())
        dialog.exec()

    def _build_corrective_actions_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("改善措施"))
        cas = _anomaly_workbench_service.list_corrective_actions(self._anomaly_id)
        if not cas:
            lay.addWidget(EmptyStateWidgetWrapper("尚未建立改善措施"))
        else:
            for ca in cas:
                lay.addWidget(self._build_ca_row(ca))
        btn_row = QHBoxLayout()
        btn_row.setSpacing(CONTROL_ROW_SPACING)
        btn_add = QPushButton("新增改善措施")
        btn_add.setAccessibleName("新增改善措施")
        apply_clickable_affordance(btn_add, tooltip="建立一筆改善措施")
        btn_add.clicked.connect(self._open_add_ca_dialog)
        btn_row.addWidget(btn_add)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return card

    def _build_ca_row(self, ca: dict) -> QWidget:
        desc = str(ca.get("description") or "—")
        status = str(ca.get("status") or "—")
        resp = str(ca.get("responsible_party") or "—")
        target = str(ca.get("target_date") or "—")
        verification_required = bool(ca.get("effectiveness_verification_required"))
        wrapper = QFrame()
        wrapper.setObjectName("AnomalyCorrectiveActionRow")
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(CONTROL_ROW_SPACING)
        meta = (
            f"負責人：{resp}　預計完成：{target}"
            + ("　需有效性驗證" if verification_required else "")
        )
        v.addWidget(self._kv(f"{desc}（{status}）", meta))

        verifications = _anomaly_workbench_service.list_effectiveness_verifications(
            ca.get("id") or ""
        )
        if verifications:
            lay_summary = QVBoxLayout()
            lay_summary.setContentsMargins(0, 0, 0, 0)
            lay_summary.setSpacing(2)
            for ver in verifications:
                line = (
                    f"· {ver.get('result') or '—'}　"
                    f"驗證人：{ver.get('verified_by') or '—'}　"
                    f"日期：{ver.get('verified_date') or '—'}"
                )
                lbl = QLabel(line)
                lbl.setProperty("role", "meta")
                lbl.setWordWrap(True)
                lay_summary.addWidget(lbl)
            v.addLayout(lay_summary)

        status_text = str(ca.get("status") or "")
        if status_text in ("已規劃", "執行中"):
            btn_row = QHBoxLayout()
            btn_row.setSpacing(CONTROL_ROW_SPACING)
            btn_complete = QPushButton("標記完成")
            btn_complete.setAccessibleName(f"完成改善措施：{desc[:24]}")
            apply_clickable_affordance(
                btn_complete,
                tooltip="將措施標記為已完成並寫入處理歷程",
            )
            btn_complete.clicked.connect(
                lambda _checked=False, cid=ca.get("id"), text=desc, vr=verification_required: (
                    self._open_complete_ca_dialog(cid, text, vr)
                )
            )
            btn_row.addWidget(btn_complete)
            btn_row.addStretch(1)
            v.addLayout(btn_row)
        if verification_required or status_text in (
            "待有效性驗證",
            "已實施",
            "有效",
            "無效",
        ):
            btn_row2 = QHBoxLayout()
            btn_row2.setSpacing(CONTROL_ROW_SPACING)
            btn_verify = QPushButton("新增驗證")
            btn_verify.setAccessibleName(f"新增有效性驗證：{desc[:24]}")
            apply_clickable_affordance(
                btn_verify, tooltip="為此措施追加一筆有效性驗證"
            )
            btn_verify.clicked.connect(
                lambda _checked=False, cid=ca.get("id"), text=desc: (
                    self._open_add_verification_dialog(cid, text)
                )
            )
            btn_row2.addWidget(btn_verify)
            btn_row2.addStretch(1)
            v.addLayout(btn_row2)
        return wrapper

    def _open_add_ca_dialog(self) -> None:
        from ui.widgets.add_corrective_action_dialog import AddCorrectiveActionDialog
        dialog = AddCorrectiveActionDialog(self._anomaly_id, self)
        dialog.ca_created.connect(lambda _id: self._refresh())
        dialog.exec()

    def _open_complete_ca_dialog(
        self,
        ca_id: str,
        description: str,
        verification_required: bool,
    ) -> None:
        from ui.widgets.complete_corrective_action_dialog import (
            CompleteCorrectiveActionDialog,
        )
        dialog = CompleteCorrectiveActionDialog(
            ca_id,
            description=description,
            verification_required=verification_required,
            parent=self,
        )
        dialog.ca_completed.connect(lambda _id: self._refresh())
        dialog.exec()

    def _open_add_verification_dialog(
        self, ca_id: str, description: str
    ) -> None:
        from ui.widgets.add_verification_dialog import AddVerificationDialog
        dialog = AddVerificationDialog(
            ca_id, description=description, parent=self
        )
        dialog.verification_created.connect(lambda _id: self._refresh())
        dialog.exec()

    def _build_8d_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("Supplier 8D 審查"))
        reviews = _anomaly_workbench_service.list_eight_d_reviews(self._anomaly_id)
        if not reviews:
            lay.addWidget(EmptyStateWidgetWrapper("尚無 Supplier 8D"))
        else:
            for review in reviews:
                rev = str(review.get("revision") or "—")
                result = str(review.get("review_status") or "")
                comment = str(review.get("review_comment") or "")
                line = f"{rev} — {result}"
                if comment:
                    line += f"（{comment}）"
                lay.addWidget(self._kv(line, ""))
        btn_row = QHBoxLayout()
        btn_row.setSpacing(CONTROL_ROW_SPACING)
        btn_add = QPushButton("追加 8D 審查")
        btn_add.setAccessibleName("追加 Supplier 8D 審查")
        apply_clickable_affordance(
            btn_add, tooltip="以 append-only 形式新增一筆 8D 審查紀錄"
        )
        btn_add.clicked.connect(self._open_add_8d_dialog)
        btn_row.addWidget(btn_add)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return card

    def _open_add_8d_dialog(self) -> None:
        from ui.widgets.add_eight_d_review_dialog import AddEightDReviewDialog
        reviews = _anomaly_workbench_service.list_eight_d_reviews(
            self._anomaly_id
        )
        next_hint = ""
        if reviews:
            last = str(reviews[-1].get("revision") or "")
            if last.upper().startswith("REV "):
                tail = last[4:].strip()
                if tail.isalpha() and tail.isascii():
                    next_char = chr(ord(tail.upper()) + 1)
                    next_hint = f"Rev {next_char}"
        dialog = AddEightDReviewDialog(
            self._anomaly_id, next_revision_hint=next_hint, parent=self
        )
        dialog.review_created.connect(lambda _id: self._refresh())
        dialog.exec()

    def _build_attachments_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("附件"))
        atts = _anomaly_workbench_service.list_attachments(self._anomaly_id)
        if not atts:
            lay.addWidget(EmptyStateWidgetWrapper("尚無附件"))
            return card
        for att in atts:
            fname = str(att.get("file_name") or "—")
            category = str(att.get("category") or "其他")
            lay.addWidget(self._kv(fname, category))
        return card

    def _build_timeline_card(self) -> QFrame:
        card = create_section_card(self)
        lay = card.layout()
        lay.addWidget(self._section_title("處理歷程"))
        timeline = _anomaly_workbench_service.list_timeline(self._anomaly_id)
        if not timeline:
            lay.addWidget(EmptyStateWidgetWrapper("尚無處理歷程"))
        else:
            for event in timeline:
                ts = str(event.get("ts") or "")
                kind = str(event.get("kind") or "")
                actor = str(event.get("actor") or "")
                summary = str(event.get("summary") or "")
                line = f"{ts} {kind}" + (f" · {actor}" if actor else "")
                lay.addWidget(self._kv(line, summary))
        btn_row = QHBoxLayout()
        btn_row.setSpacing(CONTROL_ROW_SPACING)
        btn_add = QPushButton("新增處理紀錄")
        btn_add.setAccessibleName("新增處理紀錄")
        apply_clickable_affordance(
            btn_add, tooltip="追加一筆自由格式的處理紀錄到歷程"
        )
        btn_add.clicked.connect(self._open_add_audit_dialog)
        btn_row.addWidget(btn_add)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return card

    def _open_add_audit_dialog(self) -> None:
        from ui.widgets.add_audit_log_dialog import AddAuditLogDialog
        dialog = AddAuditLogDialog(self._anomaly_id, parent=self)
        dialog.audit_created.connect(lambda _id: self._refresh())
        dialog.exec()

    # ── small helpers ─────────────────────────────────────────────────
    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "sectionTitle")
        return lbl

    def _kv(self, label: str, value: str) -> QWidget:
        inner = QFrame()
        h = QHBoxLayout(inner)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(CONTROL_ROW_SPACING)
        k = QLabel(label)
        k.setProperty("role", "meta")
        v = QLabel(value)
        v.setWordWrap(True)
        v.setProperty("role", "value")
        h.addWidget(k, 1)
        h.addWidget(v, 2)
        return inner

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("AnomalyOverviewFooter")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(
            DIALOG_HEADER_FOOTER_H_MARGIN, 10, DIALOG_HEADER_FOOTER_H_MARGIN, 14
        )
        lay.addStretch()
        close_btn = QPushButton("關閉")
        close_btn.setMinimumWidth(DIALOG_FOOTER_CLOSE_MIN_WIDTH)
        close_btn.setAccessibleName("關閉異常案件工作台概況")
        apply_clickable_affordance(close_btn, tooltip="關閉概況")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
        return footer


class EmptyStateWidgetWrapper(QLabel):
    """Small read-only empty hint used inside section cards."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setProperty("role", "helperText")
