"""Prompt and input canonicalization for SOLVENT.
Pure Python, zero external dependencies.
"""
import hashlib
import re

MAX_NARRATIVE_LENGTH = 1000
MAX_POLICY_LENGTH = 8000
DEFAULT_MAX_FETCH_CHARS = 4000

# Delimiter-impersonation tokens. The adjudication prompt wraps untrusted
# content between its own markers ([[POLICY_START]] ... [[POLICY_END]] and the
# per-evidence markers). The only injection these patterns need to defeat is
# content that fabricates those markers or a code fence. They deliberately do
# NOT strip ordinary words: an earlier version removed the literal words
# "BEGIN"/"END" and any "---", which corrupted legitimate text -- "independently"
# silently became "indep ently" on a live contract. Stripping the bracket/brace/
# fence tokens defeats marker impersonation without mangling prose.
FORBIDDEN_PATTERNS = [
    re.compile(r"`{3,}"),   # triple-backtick code fences
    re.compile(r"\[{2,}"),  # [[ marker-open impersonation
    re.compile(r"\]{2,}"),  # ]] marker-close impersonation
    re.compile(r"<{3,}"),   # <<< ... >>>
    re.compile(r">{3,}"),
]


def sanitize_text(text: str, max_length: int) -> str:
    """
    Strips control characters, prompt injection delimiters, fences,
    normalizes whitespace, and truncates to max_length.
    """
    if not isinstance(text, str):
        return ""

    # Replace newlines/tabs with space
    clean = re.sub(r"[\r\n\t]+", " ", text)
    # Remove all non-printable ASCII / control characters except standard printable
    clean = re.sub(r"[^\x20-\x7E]", " ", clean)

    # Strip fence and marker characters
    for pat in FORBIDDEN_PATTERNS:
        clean = pat.sub(" ", clean)

    # Normalize multiple spaces
    clean = re.sub(r"\s+", " ", clean).strip()

    if len(clean) > max_length:
        clean = clean[:max_length].rstrip()

    return clean


def normalize_fetch_content(
    body, status=None, max_length: int = DEFAULT_MAX_FETCH_CHARS
) -> str:
    """
    Turns a gl.nondet.web response into bounded, sanitized evidence text.

    The SDK's Response.body is `bytes | None`, never str. Passing bytes
    straight to sanitize_text() (which returns "" for any non-str) would
    silently collapse every real fetch to the empty string and force every
    on-chain adjudication to INCONCLUSIVE -- a bug the mocked LLM hides, since
    it answers regardless of the prompt. Decode here so the judge actually
    sees the page. A non-200 response is marked as non-evidence rather than
    being fed to the judge as if it were content.
    """
    if status is not None:
        try:
            code = int(status)
        except (ValueError, TypeError):
            code = 0
        if code and code != 200:
            return "[HTTP_%d]" % code

    if body is None:
        return "[EMPTY_RESPONSE]"

    if isinstance(body, (bytes, bytearray)):
        try:
            text = bytes(body).decode("utf-8", errors="replace")
        except Exception:
            text = ""
    else:
        text = str(body)

    clean = sanitize_text(text, max_length)
    return clean if clean else "[EMPTY_RESPONSE]"


def compute_policy_hash(policy_text: str) -> str:
    """
    Normalizes policy text and computes SHA-256 hex digest.
    """
    sanitized = sanitize_text(policy_text, MAX_POLICY_LENGTH)
    return hashlib.sha256(sanitized.encode("utf-8")).hexdigest()
