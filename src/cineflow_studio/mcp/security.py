"""Security, sanitization, and secret protection for CineFlow MCP Server."""
from __future__ import annotations

import re
from typing import Any

# Regex patterns for sensitive keys and tokens
SECRET_PATTERNS = [
    # CineFlow Cloud API keys
    (re.compile(r"cf_(live|test|pro)_[a-zA-Z0-9_-]{8,}", re.IGNORECASE), r"cf_\1_***REDACTED***"),
    # OpenAI / Anthropic / Kie / Generic sk- keys
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE), "sk-***REDACTED***"),
    # GitHub Tokens
    (re.compile(r"gh[pousr]_[a-zA-Z0-9]{20,}", re.IGNORECASE), "ghp_***REDACTED***"),
    # Google API Keys
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "AIza***REDACTED***"),
    # Database connection URLs with passwords
    (re.compile(r"(postgresql(?:\+asyncpg)?:\/\/[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1***\3"),
    # Private RSA/EC/OpenSSH keys
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # Bearer tokens in headers
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{16,}", re.IGNORECASE), r"\1***REDACTED***"),
]

SENSITIVE_KEY_NAMES = {
    "password", "secret", "token", "api_key", "apikey", "access_token",
    "auth", "authorization", "private_key", "secret_key"
}


def sanitize_string(text: str) -> str:
    """Masks any sensitive keys, database passwords, or auth tokens in a string."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_data(data: Any) -> Any:
    """Recursively walks data structures and redacts sensitive keys and values."""
    if isinstance(data, dict):
        sanitized_dict = {}
        for k, v in data.items():
            if "masked" in k.lower() or "redacted" in k.lower():
                sanitized_dict[k] = sanitize_string(v) if isinstance(v, str) else v
            elif any(s in k.lower() for s in SENSITIVE_KEY_NAMES) and isinstance(v, str):
                if v.startswith(("cf_live_", "cf_test_", "cf_pro_")) and len(v) > 12:
                    # Keep safe prefix and last 4 chars for user clarity, redact middle
                    sanitized_dict[k] = f"{v[:7]}...{v[-4:]}"
                else:
                    sanitized_dict[k] = "***REDACTED***"
            else:
                sanitized_dict[k] = sanitize_data(v)
        return sanitized_dict
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str):
        return sanitize_string(data)
    return data
