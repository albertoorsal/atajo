import re
import secrets
import string

ALPHABET = string.ascii_letters + string.digits # 62 chars
CODE_LEN = 7

# Valid shape for any code (generated or custom alias).
CODE_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")

# Paths that would clash with the API routes.
RESERVED_CODES = {
    "links", "health", "docs", "redoc", "openapi.json",
    "admin", "static", "favicon.ico", "robots.txt",
}


def generate_code(len : int = CODE_LEN) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(len))


def is_valid_code(code: str) -> bool:
    return bool(CODE_RE.fullmatch(code)) and code.lower() not in RESERVED_CODES
