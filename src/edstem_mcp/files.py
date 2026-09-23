import asyncio
import re
from urllib.parse import unquote, urlsplit

import httpx
from bs4 import BeautifulSoup

from edstem_mcp.catalog import EdError
from edstem_mcp.config import tls_context
from edstem_mcp.content import MAX_FILE_BYTES, extract_text, text_slice

SOURCES = {"thread", "course_thread", "resources", "lesson", "slide"}
CDN = "static.us.edusercontent.com"


def safe_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        return (
            p.scheme == "https"
            and p.netloc == CDN
            and not p.query
            and not p.fragment
            and bool(re.fullmatch(r"/(?:files|uploads)/[A-Za-z0-9_./%-]+", p.path))
            and not any(x in unquote(p.path).split("/") for x in (".", ".."))
            and not any(c in unquote(p.path) for c in "\\\r\n\x00")
        )
    except ValueError:
        return False


def attachments(data) -> list[dict]:
    found = {}

    def add(url, label=""):
        if isinstance(url, str) and safe_url(url):
            found.setdefault(
                url, {"url": url, "name": label or urlsplit(url).path.rsplit("/", 1)[-1]}
            )

    def visit(item):
        if isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            label = next(
                (item[k] for k in ["filename", "name", "title"] if isinstance(item.get(k), str)), ""
            )
            for key, value in item.items():
                if key in {"url", "file_url", "src", "href", "download_url"}:
                    add(value, label)
                elif key in {"content", "document", "passage", "outline"} and isinstance(
                    value, str
                ):
                    soup = BeautifulSoup(value, "html.parser")
                    for tag in soup.find_all(True):
                        for attr in ("href", "src", "url"):
                            add(tag.get(attr), tag.get("filename") or tag.get_text(strip=True))
                elif isinstance(value, (dict, list)):
                    visit(value)

    visit(data)
    return [dict(index=i, **item) for i, item in enumerate(found.values())]


async def list_attachments(client, operation: str, path: dict) -> dict:
    if operation not in SOURCES:
        raise EdError(
            "Attachment sources must be thread, course_thread, resources, lesson, or slide."
        )
    source = await client.read(operation, path)
    return {
        "attachments": attachments(source["data"]),
        "source_url": source["source_url"],
        "untrusted_content": True,
        "note": "Only direct US Ed CDN files are supported. External or signed links are excluded.",
    }


async def read_attachment(
    client, operation: str, path: dict, index: int, offset=0, max_chars=12000, *, transport=None
) -> dict:
    text_slice("", offset, max_chars)
    if type(index) is not int or index < 0:
        raise EdError("Attachment index must be a nonnegative integer.")
    items = (await list_attachments(client, operation, path))["attachments"]
    if index >= len(items):
        raise EdError("Attachment index not found. List attachments for this source first.")
    item = items[index]
    try:
        # A separate client never receives the Ed token or API cookies.
        async with (
            asyncio.timeout(30),
            client.slots,
            httpx.AsyncClient(
                timeout=15,
                trust_env=False,
                follow_redirects=False,
                verify=tls_context(),
                transport=transport,
            ) as http,
            http.stream("GET", item["url"], headers={"Accept": "*/*"}) as response,
        ):
            if response.status_code != 200:
                raise EdError(
                    "Attachment read failed; redirects are blocked.",
                    "file_http_error",
                    response.status_code,
                )
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_FILE_BYTES:
                    raise EdError("Attachment exceeds the 25 MiB limit.", "size_limit")
            mime = response.headers.get("content-type", "").split(";", 1)[0].lower()
            disposition = response.headers.get("content-disposition", "")
            match = re.search(r'filename="?([^";]+)', disposition)
            filename = match[1] if match else item["name"]
    except (httpx.RequestError, TimeoutError):
        raise EdError("Cannot read the attachment securely.", "connection_error") from None
    text, warning = await asyncio.to_thread(extract_text, bytes(body), filename, mime)
    return {
        "attachment": item,
        "content_type": mime,
        "warning": warning,
        "untrusted_content": True,
        **text_slice(text, offset, max_chars),
    }
