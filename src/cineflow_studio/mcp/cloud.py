"""CineFlow Cloud client for the studio MCP tools (Studio 3a, ticket #691).

One integration core reused by every hybrid tool. Base URL and key come from
the environment (``CINEFLOW_CLOUD_URL``, ``CINEFLOW_API_KEY``) or the key the
agent stored via ``cineflow_auth``. The server decides the tier and
entitlements (``GET /me``); the client never does.

Every call is one short HTTP request; retries: one, on network errors and
5xx only. Mutating calls carry an ``Idempotency-Key`` so a network failure
never repeats a paid operation on the server.
"""
from __future__ import annotations

import uuid
from typing import Any

import httpx

from cineflow_studio.mcp.billing import get_active_api_key

REQUEST_TIMEOUT_SEC = 30.0
RETRYABLE_STATUS = (500, 502, 503, 504)
JOB_TERMINAL_STATES = {"done", "completed", "failed", "cancelled", "canceled"}
JOB_POLL_INTERVAL_SEC = 2.0
JOB_WAIT_TIMEOUT_SEC = 600.0


class CloudError(Exception):
    """A CineFlow Cloud call failed; ``status`` is the HTTP status (0 = network)."""

    def __init__(self, message: str, status: int = 0, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class CloudUnavailable(CloudError):
    """The cloud endpoint could not be reached (network error or 5xx twice)."""


def cloud_configured() -> bool:
    return bool(get_active_api_key())


def _base_url() -> str:
    """The cloud endpoint comes from the environment; the package never ships one.

    (The default host of the private deployment is infrastructure data and
    must not leak into the public package - the studio guard enforces it.)"""
    import os

    url = os.getenv("CINEFLOW_CLOUD_URL", "").rstrip("/")
    if not url:
        raise CloudError("CINEFLOW_CLOUD_URL is not configured; set it to your CineFlow server URL.")
    return url


def _headers(idempotency: bool) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    key = get_active_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if idempotency:
        headers["Idempotency-Key"] = str(uuid.uuid4())
    return headers


async def request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
    *,
    idempotent: bool = False,
) -> dict[str, Any]:
    """One cloud call; returns the parsed JSON body (dict). Raises CloudError."""
    url = f"{_base_url()}{path}"
    last_error: Exception | None = None
    for attempt in (1, 2):  # one retry on network errors / 5xx
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC) as client:
                response = await client.request(method, url, json=json, headers=_headers(idempotent))
        except httpx.HTTPError as exc:
            last_error = exc
            continue
        if response.status_code >= 500 and attempt == 1:
            last_error = CloudError(f"cloud returned {response.status_code}", status=response.status_code)
            continue
        if response.status_code >= 400:
            try:
                body = response.json()
                code = body.get("code") if isinstance(body, dict) else None
                message = body.get("message") or body.get("detail") or response.text[:200]
            except ValueError:
                code, message = None, response.text[:200]
            raise CloudError(str(message), status=response.status_code, code=code)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()
    raise CloudUnavailable(f"cloud unreachable after retry: {last_error}", status=0)


async def get_me() -> dict[str, Any]:
    """The account, entitlements, and cloud flags (the client's one source of truth)."""
    return await request("GET", "/me")


async def plan_stages(project_id: str) -> dict[str, Any]:
    """The REAL stage system prompts + numeric rules (the server's own constants)."""
    return await request("GET", f"/projects/{project_id}/plan/stages")


async def plan_state(project_id: str) -> dict[str, Any]:
    """The canonical state: script lines, characters (both names), plan summary."""
    return await request("GET", f"/projects/{project_id}/plan/state")


async def propose_scenes(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """The agent's scene draft as data; per-scene machine codes for repairs."""
    return await request("POST", f"/projects/{project_id}/scenes/propose", body)


async def assemble_comfy_graph(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """The server builds the production dialect's runnable graph (Studio 6f).

    The dialect knowledge never ships in the package: describe what to build,
    receive the artifact, queue it to the local ComfyUI."""
    return await request("POST", f"/projects/{project_id}/comfy/assemble", body)


async def create_project(body: dict[str, Any]) -> dict[str, Any]:
    return await request("POST", "/projects", body, idempotent=True)


async def list_projects() -> list[dict[str, Any]]:
    result = await request("GET", "/projects")
    return result if isinstance(result, list) else result.get("projects", [])


async def upload_script(project_id: str, text: str) -> dict[str, Any]:
    return await request(
        "POST", f"/projects/{project_id}/script", {"mode": "manual", "text": text}, idempotent=True
    )


async def enqueue_job(project_id: str, job_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return await request(
        "POST", f"/projects/{project_id}/jobs", {"job_type": job_type, "params": params or {}}, idempotent=True
    )


async def get_job(job_id: str) -> dict[str, Any]:
    return await request("GET", f"/jobs/{job_id}")


async def wait_job(job_id: str, timeout_sec: float = JOB_WAIT_TIMEOUT_SEC) -> dict[str, Any]:
    """Poll the cloud job until a terminal state or the timeout; returns the last body.

    The poll loop sleeps between short GETs and holds no other resources."""
    import asyncio

    waited = 0.0
    while True:
        job = await get_job(job_id)
        status = str(job.get("status") or "").lower()
        if status in JOB_TERMINAL_STATES:
            return job
        if waited >= timeout_sec:
            return {**job, "wait_timed_out": True}
        await asyncio.sleep(JOB_POLL_INTERVAL_SEC)
        waited += JOB_POLL_INTERVAL_SEC
