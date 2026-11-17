"""CineFlow billing status for the MCP client (Studio 0a: honest billing).

The client never decides a tier and never grants entitlements locally. With a
CineFlow API key configured, the tier and entitlements are decided by the
CineFlow server on every cloud call (GET /me, Studio 2d / 3b). Without a key
the client runs in community mode: 100% local ComfyUI, free and unlimited.
"""
from __future__ import annotations

import os
from typing import Any

ENV_API_KEY = "CINEFLOW_API_KEY"
ENV_CLOUD_URL = "CINEFLOW_CLOUD_URL"
DEFAULT_BILLING_PORTAL = "https://cineflow.ai/pricing"

# The /me contract this package speaks (server.api_contract, Studio 2d). A
# server without billing/subscription/server fields predates it; the client
# warns and asks for a backend update instead of guessing at a tier.
PACKAGE_API_CONTRACT = 2

# In-memory session key if set via cineflow_auth during agent chat
_runtime_api_key: str | None = None


def get_active_api_key() -> str | None:
    return _runtime_api_key or os.getenv(ENV_API_KEY)


def set_active_api_key(key: str) -> None:
    global _runtime_api_key
    _runtime_api_key = key.strip()


def resolve_billing_status() -> dict[str, Any]:
    key = get_active_api_key()
    masked = None
    if key:
        clean_key = key.strip()
        masked = f"{clean_key[:7]}...{clean_key[-4:]}" if len(clean_key) > 11 else "..."
    has_key = bool(key)
    return {
        # The tier is decided by the CineFlow server; the client never
        # derives one from a key prefix (Studio 0a).
        "tier": None,
        "tier_name": "CineFlow Community (local ComfyUI)",
        "api_key_configured": has_key,
        "api_key_masked": masked,
        "architecture": "100% Local (client + local ComfyUI)",
        "render_backend": "Local ComfyUI (127.0.0.1:8188)",
        "credits": "Unlimited Local",
        "billing": {
            # Mirrored from GET /me when the key verifies; None here means
            # "unknown offline", not "unlimited".
            "generation_enabled": None,
            "gpu_unlimited": None,
            "credit_cap": None,
        },
        "refusal": None,
        "subscription": None,
        "payment_url": None,
        "storage": {"used_gb": None, "cap_gb": None},
        "server": {"api_rev": None, "api_contract": None},
        "compat": {
            "package_api_contract": PACKAGE_API_CONTRACT,
            "server_api_contract": None,
            "ok": None,
            "note": None,
        },
        "cloud": {
            "configured": has_key,
            "url": os.getenv(ENV_CLOUD_URL) or None,
            "tier": None,
            "entitlements": [],
            "note": (
                "The tier and entitlements are decided by the CineFlow server "
                "on each cloud call; the client never grants access locally."
            ),
        },
        "billing_portal": DEFAULT_BILLING_PORTAL,
        "message": (
            "A CineFlow API key is set. The tier and entitlements are verified "
            "by the CineFlow server when cloud access is used."
            if has_key
            else "Running in community mode on local ComfyUI (free & unlimited)."
        ),
    }


def authenticate_client(api_key: str) -> dict[str, Any]:
    key = api_key.strip()
    if not key:
        raise ValueError(
            "Field 'api_key' is required. Pass the CineFlow API key issued by "
            "the CineFlow server, or continue in community mode without a key."
        )

    set_active_api_key(key)
    return {
        # Honest by design (Studio 0a): saving a key is not verification.
        "status": "saved",
        "verified": False,
        "message": (
            "API key stored. This client does not verify tiers locally: the "
            "tier and entitlements are decided by the CineFlow server on each "
            "cloud call."
        ),
        "billing_portal": DEFAULT_BILLING_PORTAL,
    }
