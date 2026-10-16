"""Tests for canonicalization, prompt sanitization, and policy hashing.
"""
from contracts.solventlib.canonicalize import (
    compute_policy_hash,
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


def test_compute_policy_hash_deterministic():
    policy1 = "Service level agreement: 99.9% monthly availability for web API."
    policy2 = "Service level agreement: 99.9%  monthly   availability for web API."
    hash1 = compute_policy_hash(policy1)
    hash2 = compute_policy_hash(policy2)
    # Sanitization normalizes spaces
    assert hash1 == hash2
    assert len(hash1) == 64
