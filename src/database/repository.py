"""Backward-compatible facade for SQE DailyWork v2 SQLite repository."""

from __future__ import annotations

from database.schema_bootstrap import (
    ANOMALY_TRACE_FIELDS_MIGRATION_META_KEY,
    ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY,
    _ensure_anomaly_actions_v1,
    _ensure_anomaly_evidence_tables_v1,
    _normalize_defect_records_optional_work_order,
    create_schema,
    preview_anomaly_attachments_contract_v1,
    anomaly_attachments_contract_ready,
    migrate_anomaly_attachments_contract_v1,
    preview_product_records_view_is_active_v1,
    product_records_view_is_active_schema_ready,
    migrate_product_records_view_is_active_v1,
)

from database.supplier_repository import (
    canonicalize_supplier_name,
    list_suppliers,
    get_supplier,
    create_supplier_record,
    update_supplier_record,
    set_supplier_active,
    delete_supplier_record,
    list_supplier_contacts,
    add_supplier_contact,
    delete_supplier_contact,
    set_primary_contact,
    delete_supplier_records,
    consolidate_suppliers,
    ensure_supplier,
)

from database.product_repository import (
    sync_product_stage_to_events,
    sync_all_product_stages_to_events,
    sync_all_product_stages_to_events_once,
    list_product_stage_change_logs,
    list_products,
    get_product,
    create_product_record,
    update_product_record,
    set_product_active,
    delete_product_record,
    list_active_suppliers,
    list_active_products_for_supplier,
    seed_products_from_anomalies,
)

from database.anomaly_repository import (
    ANOMALY_NO_RECODE_META_KEY,
    IMPROVEMENT_DESC_MAX_LEN,
    _insert_anomaly_row,
    _next_anomaly_no,
    align_legacy_anomaly_categories,
    recode_anomaly_numbers,
    create_anomaly,
    require_anomaly,
    get_anomaly_detail,
    update_anomaly,
    update_anomaly_link,
    delete_anomaly,
    close_anomaly,
    update_anomaly_closed_at,
    reopen_anomaly,
    find_anomaly_trace_duplicate,
    validate_anomaly_number,
    preview_anomaly_no,
)

from database.anomaly_workbench_repository import (
    create_anomaly_action,
    list_anomaly_actions,
    get_anomaly_action,
    update_anomaly_action,
    complete_anomaly_action,
    cancel_anomaly_action,
    is_legacy_anomaly_action_overdue,
    get_current_anomaly_action,
    create_anomaly_analysis_note,
    list_anomaly_analysis_notes,
    get_anomaly_root_cause,
    upsert_anomaly_root_cause,
    create_corrective_action,
    list_corrective_actions,
    get_corrective_action,
    update_corrective_action,
    complete_corrective_action,
    change_corrective_action_status,
    create_effectiveness_verification,
    list_effectiveness_verifications,
    create_anomaly_attachment,
    update_anomaly_attachment,
    delete_anomaly_attachment_metadata,
    list_anomaly_attachments,
    create_anomaly_eight_d_review,
    list_anomaly_eight_d_reviews,
    append_anomaly_audit_log,
    list_anomaly_audit_logs,
    list_anomaly_timeline,
    get_anomaly_overview_card,
    count_overdue_open_anomalies,
    count_overdue_open_anomalies_by_supplier,
)

from database.visit_legacy_repository import (
    create_visit,
    get_visit_detail,
    list_visit_product_sections,
    list_visit_defect_notes,
    list_pending_visit_defect_notes,
    confirm_visit_defect_note_as_anomaly,
    update_visit,
    delete_visit,
    create_anomaly_with_visit_link,
    get_latest_visit_for_supplier_on_date,
    list_visits_by_supplier,
)

from database.event_query_repository import (
    search_global,
    list_events,
    get_dashboard_summary,
    get_monthly_stats,
    get_responsible_person_stats,
    refresh_monthly_cache,
    rebuild_all_monthly_cache,
    count_rows,
)

from database import anomaly_hypothesis_repository as _anomaly_hypothesis_repository
from database import anomaly_repeat_repository as _anomaly_repeat_repository
from database.case_action_repository import (
    cancel_case_action,
    case_actions_schema_ready,
    complete_case_action,
    create_case_action,
    get_case_action,
    get_current_case_action,
    is_anomaly_overdue as is_case_action_overdue,
    list_action_verifications,
    list_case_actions,
    migrate_case_actions_v1,
    preview_case_actions_v1_migration,
    record_action_verification,
    require_case_actions_schema,
    update_case_action,
)
from database.repo_helpers import (
    ANOMALY_ACTIONS_BACKFILL_META_KEY,
    ANOMALY_ACTIONS_MIGRATION_META_KEY,
    EVENT_SCOPE_ANOMALY_ONLY,
    EVENT_SCOPE_CLOSED_ONLY,
    EVENT_SCOPE_VALUES,
    EVENT_SCOPE_VISIT_ONLY,
    EVENT_SCOPE_VISIT_WITH_ANOMALY,
    SUPPLIER_CONSOLIDATION_META_KEY,
    _table_exists,
    get_migration_meta,
    upsert_migration_meta,
)
from database.repository_schema_helpers import has_column as _has_column

anomaly_hypotheses_schema_ready = (
    _anomaly_hypothesis_repository.anomaly_hypotheses_schema_ready
)
create_anomaly_hypothesis = _anomaly_hypothesis_repository.create_anomaly_hypothesis
get_anomaly_hypothesis = _anomaly_hypothesis_repository.get_anomaly_hypothesis
hypothesis_overview_metrics = _anomaly_hypothesis_repository.hypothesis_overview_metrics
list_anomaly_evidence_chain = _anomaly_hypothesis_repository.list_anomaly_evidence_chain
list_anomaly_hypotheses = _anomaly_hypothesis_repository.list_anomaly_hypotheses
migrate_anomaly_hypotheses_v1 = _anomaly_hypothesis_repository.migrate_anomaly_hypotheses_v1
preview_anomaly_hypotheses_v1 = (
    _anomaly_hypothesis_repository.preview_anomaly_hypotheses_v1
)
promote_hypothesis_to_root_cause = (
    _anomaly_hypothesis_repository.promote_hypothesis_to_root_cause
)
update_anomaly_hypothesis = _anomaly_hypothesis_repository.update_anomaly_hypothesis
validate_attachment_hypothesis_link = (
    _anomaly_hypothesis_repository.validate_attachment_hypothesis_link
)

anomaly_repeat_links_schema_ready = (
    _anomaly_repeat_repository.anomaly_repeat_links_schema_ready
)
backfill_all_repeat_links = _anomaly_repeat_repository.backfill_all_repeat_links
count_repeat_links_for_anomaly = _anomaly_repeat_repository.count_repeat_links_for_anomaly
count_supplier_repeat_flagged_anomalies = (
    _anomaly_repeat_repository.count_supplier_repeat_flagged_anomalies
)
list_repeat_links_for_anomaly = _anomaly_repeat_repository.list_repeat_links_for_anomaly
migrate_anomaly_repeat_links_v1 = _anomaly_repeat_repository.migrate_anomaly_repeat_links_v1
preview_anomaly_repeat_links_v1 = _anomaly_repeat_repository.preview_anomaly_repeat_links_v1
refresh_supplier_repeat_links = _anomaly_repeat_repository.refresh_supplier_repeat_links

import sqlite3


def require_repeat_links_schema(conn: sqlite3.Connection) -> None:
    if not anomaly_repeat_links_schema_ready(conn):
        raise RuntimeError(
            "需要完成 Repeat Issue 資料升級：anomaly_repeat_links_v1。"
        )
