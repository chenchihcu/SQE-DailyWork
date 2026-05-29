import pytest
from pathlib import Path
from services import attachment_manager

def test_rename_attachment(tmp_path, monkeypatch):
    # Mock DATA_DIR
    monkeypatch.setattr(attachment_manager, "DATA_DIR", tmp_path)
    # Refresh ANOMALY_ATTACHMENT_ROOT
    monkeypatch.setattr(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", tmp_path / "attachments" / "anomaly")
    
    anomaly_id = "test_rename"
    img_content = b"fake image"
    src_img = tmp_path / "original.jpg"
    src_img.write_bytes(img_content)
    
    # Import
    stored = attachment_manager.import_anomaly_attachments(anomaly_id, [src_img])
    assert len(stored) == 1
    assert stored[0].name == "original.jpg"
    
    # Set caption
    attachment_manager.set_anomaly_captions(anomaly_id, {"original.jpg": "hello"})
    
    # Rename
    success = attachment_manager.rename_anomaly_attachment(anomaly_id, "original.jpg", "new_name.jpg")
    assert success is True
    
    # Verify file
    files = attachment_manager.list_anomaly_attachments(anomaly_id)
    assert len(files) == 1
    assert files[0].name == "new_name.jpg"
    assert files[0].read_bytes() == img_content
    
    # Verify caption
    captions = attachment_manager.get_anomaly_captions(anomaly_id)
    assert captions == {"new_name.jpg": "hello"}
    
    # Verify old caption is gone
    assert "original.jpg" not in captions

def test_import_single_with_target_name(tmp_path, monkeypatch):
    monkeypatch.setattr(attachment_manager, "DATA_DIR", tmp_path)
    monkeypatch.setattr(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", tmp_path / "attachments" / "anomaly")
    
    anomaly_id = "test_import_single"
    src_img = tmp_path / "raw.png"
    src_img.write_bytes(b"png data")
    
    # Import with custom name
    stored = attachment_manager.import_single_anomaly_attachment(anomaly_id, src_img, "custom.png")
    assert stored.name == "custom.png"
    assert stored.exists()

def test_rename_case_only_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(attachment_manager, "DATA_DIR", tmp_path)
    monkeypatch.setattr(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", tmp_path / "attachments" / "anomaly")
    
    anomaly_id = "test_case"
    src_img = tmp_path / "UPPER.JPG"
    src_img.write_bytes(b"data")
    
    attachment_manager.import_anomaly_attachments(anomaly_id, [src_img])
    
    # Rename UPPER.JPG -> upper.jpg
    success = attachment_manager.rename_anomaly_attachment(anomaly_id, "UPPER.JPG", "upper.jpg")
    assert success is True
    
    files = attachment_manager.list_anomaly_attachments(anomaly_id)
    # On Windows, we check the actual case if possible, but listdir might show the change
    # Note: list_anomaly_attachments uses sorted names, we just check the output
    names = [f.name for f in files]
    assert "upper.jpg" in names
    assert "UPPER.JPG" not in names

def test_clear_caption_on_rename(tmp_path, monkeypatch):
    monkeypatch.setattr(attachment_manager, "DATA_DIR", tmp_path)
    monkeypatch.setattr(attachment_manager, "ANOMALY_ATTACHMENT_ROOT", tmp_path / "attachments" / "anomaly")
    
    anomaly_id = "test_clear"
    src_img = tmp_path / "img.jpg"
    src_img.write_bytes(b"data")
    
    attachment_manager.import_anomaly_attachments(anomaly_id, [src_img])
    attachment_manager.set_anomaly_captions(anomaly_id, {"img.jpg": "should go away"})
    
    # In AttachmentEditor.save_to_anomaly logic:
    # 1. rename
    attachment_manager.rename_anomaly_attachment(anomaly_id, "img.jpg", "new.jpg")
    # 2. update captions with empty value
    attachment_manager.set_anomaly_captions(anomaly_id, {"new.jpg": ""})
    
    captions = attachment_manager.get_anomaly_captions(anomaly_id)
    assert "new.jpg" not in captions
    assert not captions
