"""SSRF validation module for SOLVENT.
Pure Python, zero external dependencies.
"""
import ipaddress
import re
from urllib.parse import urlparse

# Strict limits
MAX_URL_LENGTH = 512
MAX_URLS_COUNT = 5
MAX_FETCH_CHARS = 4000

# Prohibited schemes, credentials, ports
ALLOWED_SCHEME = "https"
ALLOWED_PORT = 443

# Blocked special hostnames and suffixes
BLOCKED_EXACT_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
}

BLOCKED_DOMAIN_SUFFIXES = (
    ".local",
    ".internal",
    ".arpa",
    ".home.arpa",
    ".localhost",
    ".lan",
    ".test",
    ".example",
    ".invalid",
)

# Standard valid DNS hostname pattern with alphabetic TLD (min 2 chars)
HOSTNAME_REGEX = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.[A-Za-z]{2,63}$"
)


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validates a URL against strict SSRF rules.
    Returns (True, canonical_url) or (False, error_reason).
    """
    if not isinstance(url, str):
        return False, "URL must be a string"

    url = url.strip()
    if not url:
        return False, "URL cannot be empty"

    if len(url) > MAX_URL_LENGTH:
        return False, f"URL exceeds maximum length of {MAX_URL_LENGTH}"

    # Check for whitespace or control characters
    if any(c <= " " or c in "\x7f" for c in url):
        return False, "URL contains whitespace or control characters"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL parse failed: {str(e)}"

    if parsed.scheme.lower() != ALLOWED_SCHEME:
        return False, f"Only {ALLOWED_SCHEME} is allowed"

    # Reject credentials
    if parsed.username or parsed.password:
        return False, "Credentials in URL are strictly forbidden"

    if not parsed.hostname:
        return False, "URL missing host"

    host = parsed.hostname.lower().rstrip(".")

    # Port validation
    port = parsed.port
    if port is not None and port != ALLOWED_PORT:
        return False, f"Non-standard port {port} forbidden (only {ALLOWED_PORT} allowed)"

    # Block exact forbidden hosts
    if host in BLOCKED_EXACT_HOSTS:
        return False, f"Host {host} is blocked"

    # Block forbidden suffixes
    if any(host.endswith(suffix) for suffix in BLOCKED_DOMAIN_SUFFIXES):
        return False, f"Host domain suffix is blocked: {host}"

    # Check if host looks like numeric IPv4 or IPv6
    # Reject IPv6 literals immediately
    if ":" in host or "[" in host or "]" in host:
        return False, "IPv6 literals are forbidden"

    # Check if host is numeric or contains non-alphabetic TLD
    # If host looks like an IP (e.g. all digits/dots or octal/hex representation):
    is_numeric_ip = False
    # Check simple quad regex or purely digits
    parts = host.split(".")
    if all(p.isdigit() for p in parts) and len(parts) in (1, 2, 3, 4):
        is_numeric_ip = True

    if is_numeric_ip:
        # Check strict canonical decimal dotted quad
        if len(parts) != 4:
            return False, "Only canonical 4-part decimal IPv4 addresses are permitted"
        for p in parts:
            if len(p) > 1 and p.startswith("0"):
                return False, "Leading zeros in IP octets (octal notation) forbidden"
            try:
                val = int(p)
                if val < 0 or val > 255:
                    return False, "IP octet out of range 0-255"
            except ValueError:
                return False, "Invalid decimal IP octet"

        try:
            ip_obj = ipaddress.IPv4Address(host)
        except Exception:
            return False, "Invalid IPv4 address"

        # Check for private, loopback, link-local, multicast, reserved, CGNAT
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return False, f"IP address {host} belongs to a restricted/private network"

        # Explicit check for CGNAT (100.64.0.0/10)
        cgnat = ipaddress.IPv4Network("100.64.0.0/10")
        if ip_obj in cgnat:
            return False, f"IP address {host} belongs to CGNAT (100.64.0.0/10)"

        # 0.0.0.0/8 or current network
        if ip_obj in ipaddress.IPv4Network("0.0.0.0/8"):
            return False, f"IP address {host} is invalid (0.0.0.0/8)"

    else:
        # Host is a domain name. Validate using standard hostname regex with alphabetic TLD
        if not HOSTNAME_REGEX.match(host):
            return False, f"Hostname '{host}' is invalid or does not have a valid alphabetic TLD"

    # Reconstruct canonical URL (always https://host[:443]/path?query)
    # urlparse path defaults to empty; normalize to / if empty
    path = parsed.path if parsed.path else "/"
    query_str = f"?{parsed.query}" if parsed.query else ""
    canonical_url = f"https://{host}{path}{query_str}"
    return True, canonical_url


def validate_urls_list(urls: list[str]) -> tuple[bool, list[str], str]:
    """
    Validates a list of evidence URLs.
    Enforces max N urls, no duplicates, valid SSRF.
    Returns (True, canonical_urls, "") or (False, [], error_reason).
    """
    if not isinstance(urls, list):
        return False, [], "URLs must be a list"

    if len(urls) == 0:
        return False, [], "At least one evidence URL is required"

    if len(urls) > MAX_URLS_COUNT:
        return False, [], f"Exceeded maximum number of URLs ({MAX_URLS_COUNT})"

    canonical_urls = []
    seen = set()

    for u in urls:
        ok, res = validate_url(u)
        if not ok:
            return False, [], f"Invalid URL '{u}': {res}"
        if res in seen:
            return False, [], f"Duplicate URL detected: {res}"
        seen.add(res)
        canonical_urls.append(res)

    return True, canonical_urls, ""
