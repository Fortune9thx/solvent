"""Tests for SSRF validation in solventlib.
"""
import pytest
from contracts.solventlib.ssrf import validate_url, validate_urls_list


def test_valid_public_https_urls():
    valid = [
        "https://status.github.com/api/status.json",
        "https://api.cloudflare.com/client/v4/ips",
        "https://status.openai.com",
        "https://aws.amazon.com/health/status",
        "https://example.com/incident-1234?view=full&id=99",
    ]
    for u in valid:
        ok, res = validate_url(u)
        assert ok is True, f"Expected {u} to be valid, got {res}"
        assert res.startswith("https://")


def test_reject_non_https():
    invalid = [
        "http://status.github.com/api/status.json",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://example.com",
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False
        assert "Only https is allowed" in res


def test_reject_credentials():
    invalid = [
        "https://user:pass@example.com/status",
        "https://admin@api.service.com",
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False
        assert "Credentials" in res


def test_reject_non_standard_ports():
    invalid = [
        "https://example.com:8080/status",
        "https://example.com:8443/status",
        "https://example.com:80/status",
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False
        assert "Non-standard port" in res


def test_reject_localhost_and_internal_names():
    invalid = [
        "https://localhost/test",
        "https://metadata.google.internal/computeMetadata/v1",
        "https://instance-data/latest/meta-data",
        "https://server.local/api",
        "https://db.internal/status",
        "https://router.home.arpa/health",
        "https://test.invalid/health",
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False, f"Expected {u} to be blocked"


def test_reject_ipv6_literals():
    invalid = [
        "https://[::1]/status",
        "https://[fe80::1]/status",
        "https://[2001:db8::1]/status",
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False
        assert "IPv6 literals are forbidden" in res


def test_reject_private_and_special_ipv4():
    invalid = [
        "https://127.0.0.1/status",         # loopback
        "https://10.0.0.1/status",          # private
        "https://172.16.0.1/status",        # private
        "https://192.168.1.1/status",       # private
        "https://169.254.169.254/latest",   # link-local AWS metadata
        "https://100.64.0.1/status",        # CGNAT
        "https://0.0.0.0/status",           # 0.0.0.0/8
        "https://224.0.0.1/status",         # multicast
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False, f"Expected IP {u} to be blocked"


def test_reject_non_canonical_octal_decimal_ip():
    invalid = [
        "https://0177.0.0.1/status",        # octal leading zero
        "https://2130706433/status",        # single dword integer IP
        "https://127.1/status",             # 2-part IP
        "https://127.0.1/status",           # 3-part IP
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False, f"Expected non-canonical IP {u} to be blocked"


def test_reject_invalid_tld_or_bad_characters():
    invalid = [
        "https://example.c/path",           # TLD < 2 chars
        "https://bad_domain.com/path",      # underscore in domain
        "https://example..com/path",
        "https://-example.com/path",
        "https://example.com/path with space",
    ]
    for u in invalid:
        ok, res = validate_url(u)
        assert ok is False, f"Expected bad domain/char {u} to be rejected"


def test_validate_urls_list():
    # Empty list
    ok, urls, err = validate_urls_list([])
    assert ok is False
    assert "At least one" in err

    # Too many urls (> 5)
    too_many = [f"https://status{i}.example.com" for i in range(6)]
    ok, urls, err = validate_urls_list(too_many)
    assert ok is False
    assert "Exceeded maximum" in err

    # Duplicates
    dupes = ["https://status.example.com", "https://status.example.com/"]
    ok, urls, err = validate_urls_list(dupes)
    assert ok is False
    assert "Duplicate" in err

    # Valid list
    valid = ["https://status.datadoghq.com", "https://status.pagerduty.com"]
    ok, urls, err = validate_urls_list(valid)
    assert ok is True
    assert len(urls) == 2
