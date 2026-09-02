"""One-shot mechanical split of database/repository.py into domain modules.

Run from repo root:
  .venv\\Scripts\\python.exe scripts/split_repository.py
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_FILE = ROOT / "src" / "database" / "repository.py"
OUT_DIR = ROOT / "src" / "database"

MODULE_GROUPS: dict[str, list[str]] = {
    "schema_bootstrap": [
        "_ensure_supplier_category_rename_v1",
        "_ensure_supplier_category_rename_v2",
        "_ensure_product_item_category_v1",
        "_ensure_product_item_category_v2",
        "create_schema",
        "_ensure_anomaly_actions_v1",
        "_backfill_legacy_anomaly_actions",
        "_ensure_anomaly_evidence_tables_v1",
        "_create_if_missing",
        "preview_anomaly_attachments_contract_v1",
        "anomaly_attachments_contract_ready",
        "_ensure_anomaly_attachment_contract_v1",
        "migrate_anomaly_attachments_contract_v1",
        "_ensure_anomaly_trace_fields_v1",
        "_remove_anomaly_trace_supplier_unique_indexes",
        "_normalize_defect_records_optional_work_order",
        "_normalize_event_status_tables",
        "_remove_tech_transfer_columns",
        "_rebuild_anomalies_with_zh_status",
        "_rebuild_visits_with_zh_status",
        "_remove_products_spec_desc_column_if_present",
        "_rebuild_products_without_spec_desc",
        "_product_records_view_sql",
        "_product_records_view_has_is_active_filter",
        "preview_product_records_view_is_active_v1",
        "product_records_view_is_active_schema_ready",
        "migrate_product_records_view_is_active_v1",
    ],
    "supplier_repository": [
        "canonicalize_supplier_name",
        "_normalize_supplier_name_for_storage",
        "list_suppliers",
        "get_supplier",
        "create_supplier_record",
        "update_supplier_record",
        "set_supplier_active",
        "delete_supplier_record",
        "list_supplier_contacts",
        "add_supplier_contact",
        "delete_supplier_contact",
        "set_primary_contact",
        "delete_supplier_records",
        "_supplier_recency_sort_key",
        "_pick_latest_non_empty_supplier_field",
        "_pick_supplier_keeper",
        "_merge_supplier_products",
        "_consolidate_suppliers_inner",
        "consolidate_suppliers",
        "ensure_supplier",
    ],
    "product_repository": [
        "_insert_product_stage_change_log",
        "sync_product_stage_to_events",
        "_backfill_event_product_links_by_name",
        "sync_all_product_stages_to_events",
        "sync_all_product_stages_to_events_once",
        "list_product_stage_change_logs",
        "_product_recency_sort_key",
        "_pick_latest_product_name",
        "_product_select_fragments",
        "list_products",
        "get_product",
        "_ensure_product_code_globally_unique",
        "_validate_product_supplier_links",
        "create_product_record",
        "update_product_record",
        "set_product_active",
        "delete_product_record",
        "list_active_suppliers",
        "list_active_products_for_supplier",
        "seed_products_from_anomalies",
        "_next_auto_product_code",
        "_find_product_id_by_name_scope",
    ],
    "anomaly_repository": [
        "align_legacy_anomaly_categories",
        "recode_anomaly_numbers",
        "_resolve_anomaly_no_target_specs",
        "_build_recode_rows",
        "_build_old_to_new_mapping",
        "_apply_key_updates",
        "_regenerate_conflicting_nos",
        "_rewrite_text_columns",
        "_iter_text_columns",
        "_AnomalyInputs",
        "_prepare_anomaly_inputs",
        "create_anomaly",
        "require_anomaly",
        "get_anomaly_detail",
        "update_anomaly",
        "update_anomaly_link",
        "delete_anomaly",
        "close_anomaly",
        "update_anomaly_closed_at",
        "reopen_anomaly",
        "_resolve_product_selection",
        "find_anomaly_trace_duplicate",
        "validate_anomaly_number",
        "_validate_visit_supplier",
        "_normalize_optional_iso_date",
        "_insert_anomaly_row",
        "_next_anomaly_no",
        "preview_anomaly_no",
    ],
    "anomaly_workbench_repository": [
        "create_anomaly_action",
        "list_anomaly_actions",
        "get_anomaly_action",
        "update_anomaly_action",
        "complete_anomaly_action",
        "cancel_anomaly_action",
        "is_legacy_anomaly_action_overdue",
        "get_current_anomaly_action",
        "create_anomaly_analysis_note",
        "_count_analysis_note_attachments",
        "list_anomaly_analysis_notes",
        "get_anomaly_root_cause",
        "upsert_anomaly_root_cause",
        "create_corrective_action",
        "list_corrective_actions",
        "get_corrective_action",
        "update_corrective_action",
        "complete_corrective_action",
        "change_corrective_action_status",
        "create_effectiveness_verification",
        "list_effectiveness_verifications",
        "create_anomaly_attachment",
        "update_anomaly_attachment",
        "delete_anomaly_attachment_metadata",
        "_normalize_attachment_file_name",
        "list_anomaly_attachments",
        "_count_anomaly_attachment_manifest",
        "create_anomaly_eight_d_review",
        "list_anomaly_eight_d_reviews",
        "append_anomaly_audit_log",
        "list_anomaly_audit_logs",
        "list_anomaly_timeline",
        "get_anomaly_overview_card",
        "count_overdue_open_anomalies",
        "count_overdue_open_anomalies_by_supplier",
    ],
    "visit_legacy_repository": [
        "create_visit",
        "get_visit_detail",
        "list_visit_product_sections",
        "list_visit_defect_notes",
        "list_pending_visit_defect_notes",
        "confirm_visit_defect_note_as_anomaly",
        "update_visit",
        "delete_visit",
        "create_anomaly_with_visit_link",
        "get_latest_visit_for_supplier_on_date",
        "list_visits_by_supplier",
        "_normalize_visit_product_sections",
        "_normalize_visit_defect_notes",
        "_confirmed_visit_defect_note_count",
        "_replace_visit_product_sections_and_defect_notes",
        "_insert_visit_defect_note_row",
        "_defect_note_status",
        "_apply_visit_rollup",
        "_join_unique_texts",
        "_insert_visit_row",
        "_find_latest_visit_id",
        "_backfill_visit_product_sections",
    ],
    "event_query_repository": [
        "_event_period_filter",
        "search_global",
        "list_events",
        "get_dashboard_summary",
        "get_monthly_stats",
        "get_responsible_person_stats",
        "refresh_monthly_cache",
        "rebuild_all_monthly_cache",
        "count_rows",
    ],
}

MODULE_CONSTANTS: dict[str, list[str]] = {
    "schema_bootstrap": [
        "_ATTACHMENT_CONTRACT_REQUIRED_COLUMNS",
        "ANOMALY_TRACE_FIELDS_MIGRATION_META_KEY",
        "ANOMALY_TRACE_UNIQUE_INDEX_REMOVAL_META_KEY",
        "_TRACE_FIELD_COLUMNS",
        "_PRODUCT_RECORDS_VIEW_DDL",
    ],
    "anomaly_repository": [
        "ANOMALY_NO_RECODE_META_KEY",
        "IMPROVEMENT_DESC_MAX_LEN",
        "_STRICT_ISO_DATE_PATTERN",
        "_ANOMALY_NO_PATTERN",
    ],
}

MODULE_DOCSTRINGS = {
    "schema_bootstrap": "SQLite schema bootstrap, migrations, and DDL helpers for SQE DailyWork v2.",
    "supplier_repository": "Shared supplier master-data persistence.",
    "product_repository": "Shared product master-data persistence and stage sync.",
    "anomaly_repository": "Supplier-event anomaly CRUD, trace fields, and recode helpers.",
    "anomaly_workbench_repository": "Supplier-event workbench sub-table persistence and read models.",
    "visit_legacy_repository": "Legacy visit CRUD retained for tests and scripts (product UI retired).",
    "event_query_repository": "Supplier-event queries, global search projection, and monthly stats cache.",
}

COMMON_IMPORTS = textwrap.dedent(
    """
    from __future__ import annotations

    import logging
    import re
    import sqlite3
    import uuid
    from dataclasses import dataclass
    from datetime import date
    from typing import Any
    """
).strip()


def _collect_nodes(source: str) -> tuple[list[ast.stmt], dict[str, ast.stmt]]:
    tree = ast.parse(source)
    ordered: list[ast.stmt] = []
    by_name: dict[str, ast.stmt] = {}
    for node in tree.body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if name:
            by_name[name] = node
        ordered.append(node)
    return ordered, by_name


def _slice_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return "".join(lines[start:end])


def _assigned_to_module(by_name: dict[str, ast.stmt]) -> dict[str, str]:
    assigned: dict[str, str] = {}
    for module, names in MODULE_GROUPS.items():
        for name in names:
            assigned[name] = module
    for module, names in MODULE_CONSTANTS.items():
        for name in names:
            assigned[name] = module
    return assigned


def _build_module_source(
    module: str,
    source: str,
    by_name: dict[str, ast.stmt],
    names: list[str],
) -> str:
    parts = [
        f'"""{MODULE_DOCSTRINGS[module]}"""',
        "",
        COMMON_IMPORTS,
        "",
    ]
    if module == "schema_bootstrap":
        parts.append(_schema_bootstrap_imports())
    elif module == "supplier_repository":
        parts.append(_supplier_imports())
    elif module == "product_repository":
        parts.append(_product_imports())
    elif module == "anomaly_repository":
        parts.append(_anomaly_imports())
    elif module == "anomaly_workbench_repository":
        parts.append(_workbench_imports())
    elif module == "visit_legacy_repository":
        parts.append(_visit_imports())
    elif module == "event_query_repository":
        parts.append(_query_imports())
    parts.append("")
    parts.append("logger = logging.getLogger(__name__)")
    parts.append("")
    for name in names:
        node = by_name.get(name)
        if node is None:
            raise KeyError(f"{module}: missing symbol {name}")
        parts.append(_slice_source(source, node).rstrip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _schema_bootstrap_imports() -> str:
    return textwrap.dedent(
        """
        from database import anomaly_hypothesis_repository as _anomaly_hypothesis_repository
        from database import anomaly_repeat_repository as _anomaly_repeat_repository
        from database.case_action_repository import (
            case_actions_schema_ready,
            migrate_case_actions_v1,
        )
        from database.connection import disposable_runtime_enabled
        from database.product_item_category import (
            ITEM_CATEGORY_SEMI_FINISHED,
            ITEM_CATEGORY_OPTIONS,
            PRODUCT_ITEM_CATEGORY_META_KEY,
            PRODUCT_ITEM_CATEGORY_V2_META_KEY,
            infer_item_category_from_product_code,
            normalize_item_category,
        )
        from database.repo_helpers import (
            ANOMALY_ACTIONS_BACKFILL_META_KEY,
            ANOMALY_ACTIONS_MIGRATION_META_KEY,
            ANOMALY_ANALYSIS_NOTES_MIGRATION_META_KEY,
            ANOMALY_ATTACHMENTS_CONTRACT_META_KEY,
            ANOMALY_ATTACHMENTS_CONTRACT_SCHEMA_VERSION,
            ANOMALY_ATTACHMENTS_MIGRATION_META_KEY,
            ANOMALY_AUDIT_LOGS_MIGRATION_META_KEY,
            ANOMALY_EIGHT_D_REVIEWS_MIGRATION_META_KEY,
            ANOMALY_ROOT_CAUSES_MIGRATION_META_KEY,
            CORRECTIVE_ACTIONS_MIGRATION_META_KEY,
            EFFECTIVENESS_VERIFICATIONS_MIGRATION_META_KEY,
            PRODUCT_RECORDS_VIEW_IS_ACTIVE_META_KEY,
            PRODUCT_RECORDS_VIEW_IS_ACTIVE_SCHEMA_VERSION,
            _as_int,
            _table_columns,
            _table_exists,
            get_migration_meta,
            upsert_migration_meta,
        )
        from database.repository_schema_helpers import (
            ensure_column as _ensure_column,
            ensure_index as _ensure_index,
            ensure_product_indexes as _ensure_product_indexes,
            has_column as _has_column,
            table_sql as _table_sql,
        )
        from database.supplier_category import (
            LEGACY_SUPPLIER_CATEGORY_FORMAL,
            LEGACY_SUPPLIER_CATEGORY_OUTSOURCE,
            LEGACY_SUPPLIER_CATEGORY_OUTSOURCE_FACTORY_V1,
            LEGACY_SUPPLIER_CATEGORY_RAW_MATERIAL_V1,
            SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
            SUPPLIER_CATEGORY_RAW_MATERIAL,
            SUPPLIER_CATEGORY_RENAME_META_KEY,
            SUPPLIER_CATEGORY_RENAME_V2_META_KEY,
            normalize_supplier_category,
        )

        _ensure_anomaly_hypotheses_v1 = _anomaly_hypothesis_repository._ensure_anomaly_hypotheses_v1
        _ensure_anomaly_repeat_links_v1 = _anomaly_repeat_repository._ensure_anomaly_repeat_links_v1
        # _backfill_visit_product_sections imported lazily inside create_schema
        """
    ).strip()


def _supplier_imports() -> str:
    return textwrap.dedent(
        """
        from database.repo_helpers import (
            SUPPLIER_CONSOLIDATION_META_KEY,
            SupplierDeleteFailure,
            SupplierDeleteResult,
            _SUPPLIER_SUFFIX_PATTERN,
            _gen_id,
            _now_iso,
            _normalized_lookup_text,
            get_migration_meta,
            upsert_migration_meta,
        )
        from database.repository_schema_helpers import has_column as _has_column
        from database.supplier_category import (
            SUPPLIER_CATEGORY_RAW_MATERIAL,
            normalize_supplier_category,
        )
        from services.path_name_helpers import contains_invalid_path_char
        """
    ).strip()


def _product_imports() -> str:
    return textwrap.dedent(
        """
        from database.product_item_category import (
            ITEM_CATEGORY_OPTIONS,
            ITEM_CATEGORY_SEMI_FINISHED,
            infer_item_category_from_product_code,
            normalize_item_category,
        )
        from database.product_stage import (
            PRODUCT_STAGE_MASS_PRODUCTION,
            normalize_product_stage_ui,
        )
        from database.repo_helpers import (
            DEFAULT_STAGE_CHANGED_BY,
            PRODUCT_STAGE_SYNC_META_KEY,
            ProductStageSyncOnceReport,
            ProductStageSyncReport,
            STAGE_SYNC_SCOPE_ALL_HISTORY,
            _as_int,
            _build_product_lookup_by_supplier_and_name,
            _gen_id,
            _normalize_product_stage,
            _normalize_product_stage_for_read,
            _now_iso,
            get_migration_meta,
            upsert_migration_meta,
        )
        from database.repository_schema_helpers import has_column as _has_column
        from database.supplier_repository import get_supplier, list_suppliers
        from services.path_name_helpers import contains_invalid_path_char
        """
    ).strip()


def _anomaly_imports() -> str:
    return textwrap.dedent(
        """
        from database.product_stage import PRODUCT_STAGE_MASS_PRODUCTION
        from database.product_repository import get_product
        from database.repo_helpers import (
            _as_int,
            _ensure_date_not_in_future,
            _gen_id,
            _normalize_date,
            _normalize_loose_iso_date,
            _normalize_product_stage,
            _normalize_product_stage_for_read,
            _normalize_strict_iso_date,
            _now_iso,
            get_migration_meta,
            upsert_migration_meta,
        )
        from database.repository_schema_helpers import has_column as _has_column
        from services.path_name_helpers import contains_invalid_path_char
        """
    ).strip()


def _workbench_imports() -> str:
    return textwrap.dedent(
        """
        from database.anomaly_repository import require_anomaly
        from database.case_action_repository import (
            aggregate_execution_status as _aggregate_case_action_execution_status,
            aggregate_verification_status as _aggregate_action_verification_status,
            get_current_case_action,
            is_anomaly_overdue as is_case_action_overdue,
            list_case_actions,
        )
        from database.repo_helpers import (
            ANOMALY_ACTION_STATUSES,
            ANOMALY_ROOT_CAUSE_STATUSES,
            CORRECTIVE_ACTION_STATUSES,
            EFFECTIVENESS_VERIFICATION_RESULTS,
            ANOMALY_ACTION_STATUS_CANCELLED,
            ANOMALY_ACTION_STATUS_COMPLETED,
            ANOMALY_ACTION_STATUS_OPEN,
            ANOMALY_ATTACHMENT_CATEGORIES,
            ANOMALY_ATTACHMENT_CATEGORY_LABELS,
            ANOMALY_ATTACHMENT_CATEGORY_OTHER,
            ANOMALY_EVIDENCE_LABELS,
            ANOMALY_EVIDENCE_TYPES,
            ANOMALY_EVIDENCE_UNKNOWN,
            ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
            ANOMALY_ROOT_CAUSE_NOT_STARTED,
            ANOMALY_ROOT_CAUSE_VERIFIED,
            CASE_ACTION_OPEN_STATUSES,
            CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES,
            CORRECTIVE_ACTION_STATUS_IMPLEMENTED,
            CORRECTIVE_ACTION_STATUS_PLANNED,
            CORRECTIVE_ACTION_STATUS_VERIFICATION_PENDING,
            EFFECTIVENESS_VERIFICATION_RESULT_EFFECTIVE,
            EFFECTIVENESS_VERIFICATION_RESULT_INEFFECTIVE,
            EFFECTIVENESS_VERIFICATION_RESULT_PENDING,
            _gen_id,
            _normalize_strict_iso_date,
            _now_iso,
        )
        from services.path_name_helpers import contains_invalid_path_char
        """
    ).strip()


def _visit_imports() -> str:
    return textwrap.dedent(
        """
        from database.product_stage import PRODUCT_STAGE_MASS_PRODUCTION
        from database.anomaly_repository import (
            _insert_anomaly_row,
            _next_anomaly_no,
            _prepare_anomaly_inputs,
            _validate_visit_supplier,
            create_anomaly,
            require_anomaly,
        )
        from database.product_repository import get_product
        from database.repo_helpers import (
            DEFECT_NOTE_IMPROVED,
            DEFECT_NOTE_PENDING_IMPROVEMENT,
            _as_int,
            _gen_id,
            _normalize_date,
            _normalize_strict_iso_date,
            _now_iso,
        )
        from database.supplier_repository import get_supplier
        """
    ).strip()


def _query_imports() -> str:
    return textwrap.dedent(
        """
        from database.repo_helpers import (
            EVENT_SCOPE_ANOMALY_ONLY,
            EVENT_SCOPE_CLOSED_ONLY,
            EVENT_SCOPE_VALUES,
            EVENT_SCOPE_VISIT_ONLY,
            EVENT_SCOPE_VISIT_WITH_ANOMALY,
            _as_int,
            _month_from_date_value,
            _normalize_month,
            _table_exists,
        )
        from database.repository_schema_helpers import has_column as _has_column
        """
    ).strip()


def _build_facade(public_exports: dict[str, list[str]]) -> str:
    lines = [
        '"""Backward-compatible facade for SQE DailyWork v2 SQLite repository."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    for module, names in public_exports.items():
        public = [n for n in names if not n.startswith("_")]
        if not public:
            continue
        lines.append(f"from database.{module} import (")
        for name in public:
            lines.append(f"    {name},")
        lines.append(")")
        lines.append("")
    facade_private_compat: dict[str, list[str]] = {
        "schema_bootstrap": [
            "_ensure_anomaly_actions_v1",
            "_ensure_anomaly_evidence_tables_v1",
            "_normalize_defect_records_optional_work_order",
        ],
        "anomaly_repository": [
            "_insert_anomaly_row",
            "_next_anomaly_no",
        ],
    }
    for module, names in facade_private_compat.items():
        lines.append(f"from database.{module} import (")
        for name in names:
            lines.append(f"    {name},")
        lines.append(")")
        lines.append("")
    lines.extend(
        [
            "from database import anomaly_hypothesis_repository as _anomaly_hypothesis_repository",
            "from database import anomaly_repeat_repository as _anomaly_repeat_repository",
            "from database.case_action_repository import (",
            "    cancel_case_action,",
            "    case_actions_schema_ready,",
            "    complete_case_action,",
            "    create_case_action,",
            "    get_case_action,",
            "    get_current_case_action,",
            "    is_anomaly_overdue as is_case_action_overdue,",
            "    list_action_verifications,",
            "    list_case_actions,",
            "    migrate_case_actions_v1,",
            "    preview_case_actions_v1_migration,",
            "    record_action_verification,",
            "    require_case_actions_schema,",
            "    update_case_action,",
            ")",
            "from database.repo_helpers import (",
            "    ANOMALY_ACTIONS_BACKFILL_META_KEY,",
            "    ANOMALY_ACTIONS_MIGRATION_META_KEY,",
            "    EVENT_SCOPE_ANOMALY_ONLY,",
            "    EVENT_SCOPE_CLOSED_ONLY,",
            "    EVENT_SCOPE_VALUES,",
            "    EVENT_SCOPE_VISIT_ONLY,",
            "    EVENT_SCOPE_VISIT_WITH_ANOMALY,",
            "    SUPPLIER_CONSOLIDATION_META_KEY,",
            "    _table_exists,",
            "    get_migration_meta,",
            "    upsert_migration_meta,",
            ")",
            "from database.repository_schema_helpers import has_column as _has_column",
            "",
            "anomaly_hypotheses_schema_ready = (",
            "    _anomaly_hypothesis_repository.anomaly_hypotheses_schema_ready",
            ")",
            "create_anomaly_hypothesis = _anomaly_hypothesis_repository.create_anomaly_hypothesis",
            "get_anomaly_hypothesis = _anomaly_hypothesis_repository.get_anomaly_hypothesis",
            "hypothesis_overview_metrics = _anomaly_hypothesis_repository.hypothesis_overview_metrics",
            "list_anomaly_evidence_chain = _anomaly_hypothesis_repository.list_anomaly_evidence_chain",
            "list_anomaly_hypotheses = _anomaly_hypothesis_repository.list_anomaly_hypotheses",
            "migrate_anomaly_hypotheses_v1 = _anomaly_hypothesis_repository.migrate_anomaly_hypotheses_v1",
            "preview_anomaly_hypotheses_v1 = (",
            "    _anomaly_hypothesis_repository.preview_anomaly_hypotheses_v1",
            ")",
            "promote_hypothesis_to_root_cause = (",
            "    _anomaly_hypothesis_repository.promote_hypothesis_to_root_cause",
            ")",
            "update_anomaly_hypothesis = _anomaly_hypothesis_repository.update_anomaly_hypothesis",
            "validate_attachment_hypothesis_link = (",
            "    _anomaly_hypothesis_repository.validate_attachment_hypothesis_link",
            ")",
            "",
            "anomaly_repeat_links_schema_ready = (",
            "    _anomaly_repeat_repository.anomaly_repeat_links_schema_ready",
            ")",
            "backfill_all_repeat_links = _anomaly_repeat_repository.backfill_all_repeat_links",
            "count_repeat_links_for_anomaly = _anomaly_repeat_repository.count_repeat_links_for_anomaly",
            "count_supplier_repeat_flagged_anomalies = (",
            "    _anomaly_repeat_repository.count_supplier_repeat_flagged_anomalies",
            ")",
            "list_repeat_links_for_anomaly = _anomaly_repeat_repository.list_repeat_links_for_anomaly",
            "migrate_anomaly_repeat_links_v1 = _anomaly_repeat_repository.migrate_anomaly_repeat_links_v1",
            "preview_anomaly_repeat_links_v1 = _anomaly_repeat_repository.preview_anomaly_repeat_links_v1",
            "refresh_supplier_repeat_links = _anomaly_repeat_repository.refresh_supplier_repeat_links",
            "",
            "import sqlite3",
            "",
            "",
            "def require_repeat_links_schema(conn: sqlite3.Connection) -> None:",
            "    if not anomaly_repeat_links_schema_ready(conn):",
            '        raise RuntimeError(',
            '            "需要完成 Repeat Issue 資料升級：anomaly_repeat_links_v1。"',
            "        )",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    source = REPO_FILE.read_text(encoding="utf-8")
    _, by_name = _collect_nodes(source)
    assigned = _assigned_to_module(by_name)

    all_exports: dict[str, list[str]] = {}
    for module, names in MODULE_GROUPS.items():
        const_names = MODULE_CONSTANTS.get(module, [])
        ordered_names = const_names + names
        all_exports[module] = ordered_names
        module_source = _build_module_source(module, source, by_name, ordered_names)
        out_path = OUT_DIR / f"{module}.py"
        out_path.write_text(module_source, encoding="utf-8")
        print(f"wrote {out_path} ({len(module_source.splitlines())} lines)")

    facade = _build_facade(all_exports)
    REPO_FILE.write_text(facade, encoding="utf-8")
    print(f"wrote facade {REPO_FILE} ({len(facade.splitlines())} lines)")


if __name__ == "__main__":
    main()
