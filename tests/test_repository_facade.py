from __future__ import annotations

import unittest

from database import repository


class RepositoryFacadeTests(unittest.TestCase):
    def test_public_facade_symbols_remain_importable(self) -> None:
        required = (
            "create_schema",
            "list_events",
            "search_global",
            "create_anomaly",
            "close_anomaly",
            "get_anomaly_overview_card",
            "list_case_actions",
            "refresh_monthly_cache",
            "get_migration_meta",
            "upsert_migration_meta",
            "_has_column",
            "ANOMALY_ACTIONS_MIGRATION_META_KEY",
            "ANOMALY_ACTIONS_BACKFILL_META_KEY",
            "_ensure_anomaly_actions_v1",
            "_ensure_anomaly_evidence_tables_v1",
            "_normalize_defect_records_optional_work_order",
            "_insert_anomaly_row",
            "_next_anomaly_no",
            "_table_exists",
        )
        for name in required:
            with self.subTest(name=name):
                self.assertTrue(hasattr(repository, name), msg=f"missing {name}")
