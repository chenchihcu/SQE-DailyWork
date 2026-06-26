"""訪廠對話框的技轉(技術移轉)管理 Mixin。

從 NewVisitDialog 提取技轉要目確認的卡片管理、狀態正規化、
訊號同步等方法，透過多重繼承注入回原對話框。
"""

from __future__ import annotations

from ui.widgets.defect_form_widgets import (
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_YES,
    VISIT_TECH_TRANSFER_ITEMS,
)


class _VisitTechTransferMixin:
    """提供訪廠對話框的技轉(技術移轉)要目管理。

    透過多重繼承與 NewVisitDialog 組合使用：
        class NewVisitDialog(QDialog, SupplierProductFormMixin, _VisitTechTransferMixin):
            ...

    方法會透過 self 存取主對話框提供的以下屬性/方法：
    - self._tech_transfer_cards
    - self._tech_transfer_groups
    - self._syncing_tech_transfer
    - self.tech_transfer_check
    """

    # ── 單一項目讀寫 ─────────────────────────────────────

    def _set_tech_transfer_item(self, field_key: str, has_value: bool) -> None:
        """Legacy bool setter — preserved for callers passing bools."""
        card = self._tech_transfer_cards.get(field_key)
        if card is not None:
            card.set_value(has_value)
            return
        group = self._tech_transfer_groups.get(field_key)
        if group is None:
            return
        button = group.button(1 if has_value else 0)
        if button is not None:
            button.setChecked(True)

    def _set_tech_transfer_state(self, field_key: str, state: str) -> None:
        card = self._tech_transfer_cards.get(field_key)
        if card is not None:
            card.set_state(state)

    def _get_tech_transfer_item(self, field_key: str) -> bool:
        """Legacy bool getter for any caller that still expects True/False."""
        return self._get_tech_transfer_state(field_key) == TECH_TRANSFER_STATE_YES

    def _get_tech_transfer_state(self, field_key: str) -> str:
        card = self._tech_transfer_cards.get(field_key)
        if card is not None:
            return card.get_state()
        group = self._tech_transfer_groups.get(field_key)
        if group is None:
            return TECH_TRANSFER_STATE_NO
        checked = group.checkedButton()
        if checked is None:
            return TECH_TRANSFER_STATE_NO
        btn_id = group.id(checked)
        if btn_id == 1:
            return TECH_TRANSFER_STATE_YES
        if btn_id == 2:
            return TECH_TRANSFER_STATE_NA
        return TECH_TRANSFER_STATE_NO

    # ── Payload 正規化 ───────────────────────────────────

    def _normalized_tech_transfer_payload(
        self, *, tech_transfer: bool, item_states: dict[str, str]
    ) -> dict:
        normalized_states = {
            key: (
                item_states.get(key)
                if item_states.get(key)
                in (TECH_TRANSFER_STATE_YES, TECH_TRANSFER_STATE_NO, TECH_TRANSFER_STATE_NA)
                else TECH_TRANSFER_STATE_NO
            )
            for key, _ in VISIT_TECH_TRANSFER_ITEMS
        }
        normalized_tech_transfer = bool(tech_transfer) or any(
            v == TECH_TRANSFER_STATE_YES for v in normalized_states.values()
        )
        if not normalized_tech_transfer:
            normalized_states = {
                key: TECH_TRANSFER_STATE_NO for key, _ in VISIT_TECH_TRANSFER_ITEMS
            }
        result: dict = {key: normalized_states[key] for key in normalized_states}
        # Preserve the legacy boolean-shaped keys callers used to read from this
        # mapping; the new `states` key is the canonical tri-state map.
        for key, _ in VISIT_TECH_TRANSFER_ITEMS:
            result[f"_{key}_bool"] = (
                normalized_states[key] == TECH_TRANSFER_STATE_YES
            )
        result["tech_transfer"] = normalized_tech_transfer
        result["states"] = dict(normalized_states)
        # Backwards-compat boolean keys (drop underscore prefix) for older
        # callers; equal to states[key] == 'yes'.
        for key, _ in VISIT_TECH_TRANSFER_ITEMS:
            result.pop(f"_{key}_bool", None)
            result[key] = normalized_states[key] == TECH_TRANSFER_STATE_YES
        return result

    def _apply_tech_transfer_payload(
        self,
        *,
        tech_transfer: bool,
        item_states: dict[str, str] | None = None,
        item_flags: dict[str, bool] | None = None,
    ) -> None:
        if item_states is None:
            states = {
                key: (
                    TECH_TRANSFER_STATE_YES
                    if (item_flags or {}).get(key)
                    else TECH_TRANSFER_STATE_NO
                )
                for key, _ in VISIT_TECH_TRANSFER_ITEMS
            }
        else:
            states = dict(item_states)
        normalized = self._normalized_tech_transfer_payload(
            tech_transfer=tech_transfer,
            item_states=states,
        )
        self._syncing_tech_transfer = True
        try:
            self.tech_transfer_check.setChecked(normalized["tech_transfer"])
            for key, _ in VISIT_TECH_TRANSFER_ITEMS:
                self._set_tech_transfer_state(key, normalized["states"][key])
        finally:
            self._syncing_tech_transfer = False

    # ── 訊號同步 ─────────────────────────────────────────

    def _on_tech_transfer_toggled(self, checked: bool) -> None:
        if self._syncing_tech_transfer:
            return
        if checked:
            return
        self._syncing_tech_transfer = True
        try:
            for key, _ in VISIT_TECH_TRANSFER_ITEMS:
                self._set_tech_transfer_item(key, False)
        finally:
            self._syncing_tech_transfer = False

    def _on_any_tech_transfer_item_toggled(self, checked: bool) -> None:
        if not checked or self._syncing_tech_transfer:
            return
        if self.tech_transfer_check.isChecked():
            return
        self._syncing_tech_transfer = True
        try:
            self.tech_transfer_check.setChecked(True)
        finally:
            self._syncing_tech_transfer = False
