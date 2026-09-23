import time

from edstem_mcp.catalog import EdError
from edstem_mcp.content import html_text


def content_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(content_text(x) for x in value)
    if not isinstance(value, dict):
        return ""
    parts = []
    for key, item in value.items():
        if key in {"title", "name", "category", "subcategory", "outline", "passage", "text"}:
            if isinstance(item, str):
                parts.append(item)
        elif key == "content" or (key == "document" and not value.get("content")):
            if isinstance(item, str):
                parts.append(html_text(item))
        elif isinstance(item, (dict, list)):
            parts.append(content_text(item))
    return "\n".join(p for p in parts if p)


async def search_threads(
    client,
    course_id: int,
    text: str,
    offset=0,
    limit=10,
    include_replies=False,
    kind=None,
    category=None,
) -> dict:
    if not text.strip() or len(text) > 300:
        raise EdError("Search text must contain 1-300 characters.")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise EdError("Search limit must be 1-20 threads per call.")
    if kind not in (None, "post", "question", "announcement"):
        raise EdError("Search kind must be post, question, or announcement.")
    terms = text.casefold().split()
    page = await client.read(
        "threads", {"course_id": course_id}, {"limit": limit, "offset": offset, "sort": "new"}
    )
    rows = page["data"]["threads"]
    matches, scanned = [], 0
    started = time.monotonic()
    for row in rows:
        if time.monotonic() - started > 25:
            break
        scanned += 1
        if (kind and row.get("type") != kind) or (category and row.get("category") != category):
            continue
        if include_replies:
            row = (await client.read("thread", {"thread_id": row["id"]}))["data"]["thread"]
        body = content_text(row)
        if all(term in body.casefold() for term in terms):
            hit = {
                k: row[k]
                for k in [
                    "id",
                    "number",
                    "title",
                    "type",
                    "category",
                    "created_at",
                    "updated_at",
                    "reply_count",
                ]
                if k in row
            }
            hit["source_url"] = (
                f"https://edstem.org/us/courses/{course_id}/discussion/{row.get('number', '')}"
            )
            hit["excerpt"] = body[:800]
            matches.append(hit)
    more = scanned < len(rows) or page["pagination"]["next_query"] is not None
    return {
        "matches": matches,
        "scanned_threads": scanned,
        "next_offset": offset + scanned if more else None,
        "reached_end": not more,
        "untrusted_content": True,
        "scope": "Post bodies and replies" if include_replies else "Post bodies only",
        "note": "Local AND keyword matching. This page is not a complete course search. "
        "Continue next_offset until null; concurrent new posts can shift offsets.",
    }
