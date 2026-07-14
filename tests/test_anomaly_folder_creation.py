from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from services.event import _anomaly_folder
from services.event import _anomaly_service
from services.event import _visit_service


def test_create_anomaly_creates_supplier_number_folder(tmp_path: Path) -> None:
    supplier = {"supplier_name": "供應商甲", "is_active": 1}
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(_anomaly_service, "_require_supplier_record", return_value=supplier),
        patch.object(_anomaly_service, "_require_product_id", return_value="product-1"),
        patch.object(_anomaly_service, "_resolve_product_name", return_value="產品"),
        patch.object(_anomaly_service.repository, "create_anomaly", return_value="20260714001"),
    ):
        result = _anomaly_service.create_anomaly(
            {"supplier_id": "supplier-1", "product_id": "product-1", "problem_desc": "異常"}
        )

    assert result == "20260714001"
    assert (tmp_path / "供應商甲20260714001").is_dir()


def test_linked_anomaly_sanitizes_invalid_supplier_filename_chars(tmp_path: Path) -> None:
    supplier = {"supplier_name": "供應商/甲", "is_active": 1}
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(_anomaly_service, "_require_supplier_record", return_value=supplier),
        patch.object(_anomaly_service, "_require_product_id", return_value="product-1"),
        patch.object(_anomaly_service, "_resolve_product_name", return_value="產品"),
        patch.object(
            _anomaly_service.repository,
            "create_anomaly_with_visit_link",
            return_value={"anomaly_no": "20260714002", "anomaly_id": "a-2"},
        ),
    ):
        _anomaly_service.create_anomaly_with_visit_link(
            {"supplier_id": "supplier-1", "product_id": "product-1", "problem_desc": "異常"}
        )

    assert (tmp_path / "供應商_甲20260714002").is_dir()


def test_visit_defect_confirmation_creates_anomaly_folder(tmp_path: Path) -> None:
    result = {"anomaly_no": "20260714003", "anomaly_id": "a-3"}
    detail = {"supplier_name": "訪廠供應商"}
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(
            _visit_service.repository,
            "confirm_visit_defect_note_as_anomaly",
            return_value=result,
        ),
        patch.object(_visit_service.repository, "get_anomaly_detail", return_value=detail),
    ):
        actual = _visit_service.confirm_visit_defect_note_as_anomaly("note-1")

    assert actual == result
    assert (tmp_path / "訪廠供應商20260714003").is_dir()
