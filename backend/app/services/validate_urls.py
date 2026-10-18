from urllib.parse import urlparse
import ipaddress

MAX_URL_LENGTH = 2048
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal")


def validate_target_url(url:str) -> str:
    """Allow only public http(s) destinations. Raises ValueError otherwise."""
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValueError("URL is too long")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL has no host")
    if host == "localhost" or host.endswith(BLOCKED_SUFFIXES):
        raise ValueError("Destination not allowed")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url  # a domain name, not an IP literal

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise ValueError("Destination not allowed")
    return url
