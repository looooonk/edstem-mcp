import asyncio
import json

import httpx

from edstem_mcp.catalog import EdError, operation, prepare
from edstem_mcp.config import BASE_URL, Settings, tls_context

MAX_API_BYTES = 8 * 1024 * 1024


class EdClient:
    def __init__(self, settings: Settings, *, transport=None):
        self.settings = settings
        self.http = httpx.AsyncClient(
            timeout=15,
            follow_redirects=False,
            trust_env=False,
            verify=tls_context(),
            transport=transport,
        )
        self.slots = asyncio.Semaphore(2)

    async def close(self):
        await self.http.aclose()

    async def read(self, name: str, path: dict | None = None, query: dict | None = None) -> dict:
        endpoint, params = prepare(
            name, path if path is not None else {}, query if query is not None else {}
        )
        try:
            async with asyncio.timeout(35), self.slots:
                data = await self._get(endpoint, params)
        except (httpx.RequestError, TimeoutError):
            raise EdError(
                "Cannot reach Ed securely; check connectivity and retry.", "connection_error"
            ) from None
        op = operation(name)
        next_query = None
        required = {
            "user": {"user": dict, "courses": list},
            "course": {"course": dict},
            "thread": {"thread": dict},
            "course_thread": {"thread": dict},
            "lesson": {"lesson": dict},
            "slide": {"slide": dict},
            "user_stats": {"stats": dict},
        }
        if any(not isinstance(data.get(k), typ) for k, typ in required.get(name, {}).items()):
            raise EdError("Ed's response shape changed; required data is missing.", "schema_error")
        if op.collection and not isinstance(data.get(op.collection), list):
            raise EdError("Ed's response shape changed; collection is missing.", "schema_error")
        if op.paginated and len(data[op.collection]) >= params["limit"]:
            next_query = params | {"offset": params["offset"] + len(data[op.collection])}
        return {
            "operation": name,
            "data": data,
            "source_url": BASE_URL + endpoint,
            "untrusted_content": True,
            "pagination": {
                "next_query": next_query,
                "note": "An extra empty page may be needed; results can change.",
            },
        }

    async def _get(self, endpoint: str, params: dict) -> dict:
        for attempt in range(2):
            async with self.http.stream(
                "GET",
                BASE_URL + endpoint,
                params=params,
                headers={
                    "Authorization": "Bearer " + self.settings.token,
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
            ) as response:
                if response.status_code in (502, 503, 504) and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                if response.status_code != 200:
                    messages = {
                        400: "Ed rejected this read or its parameters.",
                        401: "Ed authentication failed. Check the local token.",
                        403: "Ed denied access; this is not evidence of missing data.",
                        404: "Resource not found or not visible to this account.",
                        429: "Ed rate limit reached. Wait before retrying.",
                    }
                    raise EdError(
                        messages.get(
                            response.status_code, "Ed read failed; redirects are blocked."
                        ),
                        "http_error",
                        response.status_code,
                    )
                if "json" not in response.headers.get("content-type", "").lower():
                    raise EdError("Ed returned a non-JSON response.", "schema_error")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_API_BYTES:
                        raise EdError("Response exceeds 8 MiB. Use a smaller page.", "size_limit")
                try:
                    data = json.loads(body)
                except ValueError:
                    raise EdError("Ed returned invalid JSON.", "schema_error") from None
                if not isinstance(data, dict):
                    raise EdError("Ed returned an unexpected response shape.", "schema_error")
                return data
        raise EdError("Ed is temporarily unavailable.", "http_error")
