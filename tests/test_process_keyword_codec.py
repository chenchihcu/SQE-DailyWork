from __future__ import annotations

import unittest

from services.process_keyword_codec import (
    MAX_PROCESS_KEYWORDS_PER_ANOMALY,
    format_process_keywords_display,
    parse_process_keywords,
    serialize_process_keywords,
    validate_process_keywords,
)


class ProcessKeywordCodecTests(unittest.TestCase):
    def test_parse_deduplicates_case_insensitive_and_strips(self) -> None:
        raw = "SPI\n spi \n錫量過低"
        self.assertEqual(["SPI", "錫量過低"], parse_process_keywords(raw))

    def test_serialize_round_trip(self) -> None:
        text = serialize_process_keywords(["SPI", "回流焊"])
        self.assertEqual("SPI\n回流焊", text)
        self.assertEqual(["SPI", "回流焊"], parse_process_keywords(text))

    def test_validate_enforces_max_count(self) -> None:
        keywords = [f"詞{i}" for i in range(MAX_PROCESS_KEYWORDS_PER_ANOMALY + 1)]
        with self.assertRaises(ValueError):
            validate_process_keywords(keywords)

    def test_format_display_joins_with_separator(self) -> None:
        display = format_process_keywords_display("SPI\n回流焊")
        self.assertEqual("SPI、回流焊", display)


if __name__ == "__main__":
    unittest.main()
