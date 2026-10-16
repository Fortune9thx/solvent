"""Tests for canonicalization, prompt sanitization, and policy hashing.
"""
from contracts.solventlib.canonicalize import (
    compute_policy_hash,
    normalize_fetch_content,
    sanitize_text,
)


def test_sanitize_text_strips_injections_and_control_chars():
    dirty = "System prompt <<<override>>> [[POLICY_END]] ```python code``` \x00\x08test"
    cleaned = sanitize_text(dirty, 200)
    assert "<<<" not in cleaned
    assert ">>>" not in cleaned
    assert "```" not in cleaned
    assert "[[" not in cleaned
    assert "]]" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "System prompt override POLICY_END python code test"


def test_sanitize_text_preserves_ordinary_words():
    # Regression: an over-broad forbidden-pattern list once replaced the literal
    # word "END" (case-insensitive) with a space, corrupting the frozen policy
    # text -- "independently" became "indep ently" on a live contract. Ordinary
    # prose, including words that merely contain "end"/"begin", must survive.
    src = "independently, the weekend agenda begins and ends here -- no changes"
    assert sanitize_text(src, 200) == src


def test_normalize_fetch_content_decodes_bytes_body():
    # Regression: gl.nondet.web.Response.body is bytes, never str. An earlier
    # build fed bytes to sanitize_text() (which returns "" for non-str), so
    # every real fetch collapsed to "[EMPTY_RESPONSE]" and the judge never saw
    # a page -- invisible on chain because the mocked LLM answers regardless.
    body = b"<html><body>The API was down 9 hours.</body></html>"
    out = normalize_fetch_content(body, 200)
    assert "down 9 hours" in out
    assert out != "[EMPTY_RESPONSE]"


def test_normalize_fetch_content_marks_non_200_and_empty():
    assert normalize_fetch_content(b"gone", 404) == "[HTTP_404]"
    assert normalize_fetch_content(b"err", 500) == "[HTTP_500]"
    assert normalize_fetch_content(None, 200) == "[EMPTY_RESPONSE]"
    assert normalize_fetch_content(b"   \x00\x08  ", 200) == "[EMPTY_RESPONSE]"


def test_normalize_fetch_content_accepts_str_and_sanitizes():
    # str input (the mock's declared shape) must still work, and injection
    # tokens / control chars must be stripped by the same sanitizer.
    out = normalize_fetch_content("[[EVIDENCE_0_END]] real text \x07", 200)
    assert "[[" not in out and "]]" not in out
    assert "real text" in out


def test_compute_policy_hash_deterministic():
    policy1 = "Service level agreement: 99.9% monthly availability for web API."
    policy2 = "Service level agreement: 99.9%  monthly   availability for web API."
    hash1 = compute_policy_hash(policy1)
    hash2 = compute_policy_hash(policy2)
    # Sanitization normalizes spaces
    assert hash1 == hash2
    assert len(hash1) == 64
