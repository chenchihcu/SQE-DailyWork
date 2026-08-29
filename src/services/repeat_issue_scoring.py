"""Deterministic repeat-issue similarity scoring (no database imports)."""

from __future__ import annotations

import re

from services.process_keyword_codec import parse_process_keywords

REPEAT_SCORE_CATEGORY = 40
REPEAT_SCORE_PRODUCT = 30
REPEAT_SCORE_PRODUCT_NAME = 15
REPEAT_SCORE_KEYWORD_EACH = 10
REPEAT_SCORE_KEYWORD_MAX = 30
REPEAT_SCORE_DESC_TOKEN_EACH = 5
REPEAT_SCORE_DESC_TOKEN_MAX = 25
REPEAT_MIN_SCORE = REPEAT_SCORE_CATEGORY
REPEAT_DESC_TOKEN_MIN_SHARED = 2

_PROBLEM_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]{2,}")


def _problem_tokens(text: object) -> set[str]:
    return {
        token.casefold()
        for token in _PROBLEM_TOKEN_RE.findall(str(text or ""))
    }


def compute_repeat_similarity(current: dict, peer: dict) -> tuple[int, list[str]]:
    """Return deterministic score and human-readable match reasons."""
    score = 0
    reasons: list[str] = []

    category = str(current.get("category") or "").strip()
    peer_category = str(peer.get("category") or "").strip()
    if category and peer_category and category == peer_category:
        score += REPEAT_SCORE_CATEGORY
        reasons.append("相同異常類別")

    product_id = str(current.get("product_id") or "").strip()
    peer_product_id = str(peer.get("product_id") or "").strip()
    if product_id and peer_product_id and product_id == peer_product_id:
        score += REPEAT_SCORE_PRODUCT
        reasons.append("相同料號產品")
    else:
        product_name = str(current.get("product_name") or "").strip()
        peer_product_name = str(peer.get("product_name") or "").strip()
        if product_name and peer_product_name and product_name == peer_product_name:
            score += REPEAT_SCORE_PRODUCT_NAME
            reasons.append("相同品名")

    keyword_tokens = {
        token.casefold()
        for token in parse_process_keywords(current.get("process_keywords"))
    }
    peer_keyword_tokens = {
        token.casefold()
        for token in parse_process_keywords(peer.get("process_keywords"))
    }
    shared_keywords = keyword_tokens & peer_keyword_tokens
    if shared_keywords:
        keyword_score = min(
            len(shared_keywords) * REPEAT_SCORE_KEYWORD_EACH,
            REPEAT_SCORE_KEYWORD_MAX,
        )
        score += keyword_score
        reasons.append("共同製程關鍵詞")

    shared_problem_tokens = _problem_tokens(current.get("problem_desc")) & _problem_tokens(
        peer.get("problem_desc")
    )
    if len(shared_problem_tokens) >= REPEAT_DESC_TOKEN_MIN_SHARED:
        desc_score = min(
            len(shared_problem_tokens) * REPEAT_SCORE_DESC_TOKEN_EACH,
            REPEAT_SCORE_DESC_TOKEN_MAX,
        )
        score += desc_score
        reasons.append("問題描述相似")

    return score, reasons
