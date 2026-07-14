from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from services.event import _anomaly_folder
from services.event import _anomaly_markdown


def _detail(**overrides) -> dict:
    detail = {field: "" for field, _label in _anomaly_markdown.ANOMALY_FIELDS}
    detail.update(
        {
            "id": "anomaly-1",
            "supplier_name": "供應商甲",
            "anomaly_no": "20260714001",
            "batch_qty": 0,
            "is_tech_transfer": False,
            "quality_report_required": None,
        }
    )
    detail.update(overrides)
    return detail


def test_write_anomaly_markdown_creates_named_yaml_file(tmp_path: Path) -> None:
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "list_anomaly_attachments",
            return_value=[],
        ),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "get_anomaly_captions",
            return_value={},
        ),
    ):
        result = _anomaly_markdown.write_anomaly_markdown(_detail())

    assert result == tmp_path / "供應商甲20260714001" / "供應商甲20260714001.md"
    text = result.read_text(encoding="utf-8")
    assert text.startswith("---\n異常事件:\n")
    assert '  異常單號: "20260714001"' in text
    assert '  改善說明: ""' in text
    assert '  是否要求品質異常單: ""' in text
    assert '  是否技術移轉: "否"' in text
    assert "  附件: []" in text
    parsed = yaml.safe_load(text)
    assert parsed["異常事件"]["改善說明"] == ""
    assert list(parsed["異常事件"])[-1] == "附件"


def test_markdown_sanitizes_invalid_supplier_filename_chars(tmp_path: Path) -> None:
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "list_anomaly_attachments",
            return_value=[],
        ),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "get_anomaly_captions",
            return_value={},
        ),
    ):
        result = _anomaly_markdown.write_anomaly_markdown(
            _detail(supplier_name="供應商/甲", anomaly_no="20260714002")
        )

    assert result.name == "供應商_甲20260714002.md"


def test_markdown_lists_attachments_and_captions(tmp_path: Path) -> None:
    image = tmp_path / "evidence.png"
    image.write_bytes(b"png")
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "list_anomaly_attachments",
            return_value=[image],
        ),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "get_anomaly_captions",
            return_value={"evidence.png": "現場照片"},
        ),
    ):
        result = _anomaly_markdown.write_anomaly_markdown(_detail())

    text = result.read_text(encoding="utf-8")
    assert '    - 檔名: "evidence.png"' in text
    assert '      圖說: "現場照片"' in text


def test_write_anomaly_markdown_overwrites_changed_values(tmp_path: Path) -> None:
    with (
        patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "list_anomaly_attachments",
            return_value=[],
        ),
        patch.object(
            _anomaly_markdown.attachment_manager,
            "get_anomaly_captions",
            return_value={},
        ),
    ):
        result = _anomaly_markdown.write_anomaly_markdown(_detail(status="待處理"))
        _anomaly_markdown.write_anomaly_markdown(
            _detail(
                status="已結案",
                improvement_desc="完成改善",
                root_cause_category="製程",
                closed_at="2026-07-14",
            )
        )

    parsed = yaml.safe_load(result.read_text(encoding="utf-8"))["異常事件"]
    assert parsed["狀態"] == "已結案"
    assert parsed["改善說明"] == "完成改善"
    assert parsed["原因分類"] == "製程"
    assert parsed["結案日期"] == "2026-07-14"


def test_relocate_anomaly_folder_renames_folder_and_markdown(tmp_path: Path) -> None:
    old_folder = tmp_path / "舊供應商20260714001"
    old_folder.mkdir()
    old_markdown = old_folder / "舊供應商20260714001.md"
    old_markdown.write_text("old", encoding="utf-8")

    with patch.object(_anomaly_folder, "ANOMALY_FOLDER_ROOT", tmp_path):
        result = _anomaly_folder.relocate_anomaly_folder(
            old_supplier_name="舊供應商",
            old_anomaly_no="20260714001",
            new_supplier_name="新供應商",
            new_anomaly_no="20260715001",
        )

    assert result == tmp_path / "新供應商20260715001"
    assert (result / "新供應商20260715001.md").read_text(encoding="utf-8") == "old"
    assert not old_folder.exists()
