from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from services.problem_photo_link_codec import (
    PROBLEM_PHOTO_LINKS_FILENAME,
    get_problem_photo_links,
    parse_problem_desc_items,
    set_problem_photo_links,
)


class ProblemPhotoLinkCodecTests(unittest.TestCase):
    def test_parse_problem_desc_items_strips_numbering(self) -> None:
        text = "1. 爆板\n2. 偏移"
        self.assertEqual(["爆板", "偏移"], parse_problem_desc_items(text))

    def test_set_and_get_roundtrip(self) -> None:
        anomaly_id = f"codec-{uuid4().hex}"
        folder = Path("scratch") / f"links-{uuid4().hex}"
        folder.mkdir(parents=True, exist_ok=True)
        with mock.patch(
            "services.problem_photo_link_codec.attachment_manager._anomaly_dir",
            return_value=folder,
        ), mock.patch(
            "services.problem_photo_link_codec._prune_links",
            side_effect=lambda links, _aid: links,
        ), mock.patch(
            "services.problem_photo_link_codec.attachment_manager._sync_anomaly_markdown"
        ):
            set_problem_photo_links(anomaly_id, {"a.png": 1, "b.png": 2})
            self.assertEqual(
                {"a.png": 1, "b.png": 2},
                get_problem_photo_links(anomaly_id),
            )
            path = folder / PROBLEM_PHOTO_LINKS_FILENAME
            self.assertTrue(path.is_file())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(1, payload["version"])
        if folder.exists():
            for child in folder.iterdir():
                child.unlink()
            folder.rmdir()


if __name__ == "__main__":
    unittest.main()
