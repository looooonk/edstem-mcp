"""Explicit read-only live checks through MCP stdio. Print only safe summary metadata."""

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from edstem_mcp.client import EdClient
from edstem_mcp.config import Settings
from edstem_mcp.diagnostics import ErrorLog
from edstem_mcp.files import attachments
from edstem_mcp.search import content_text

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"


async def main():
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    summary = {"transport": "stdio", "read_only": True}
    expected = {}
    server = StdioServerParameters(
        command=str(ROOT / ".venv/bin/edstem-mcp"), args=["--env-file", str(ROOT / ".env")]
    )
    with (LOCAL / "mcp-stderr.log").open("w") as err:
        async with (
            stdio_client(server, errlog=err) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            assert len(listed.tools) == 8
            assert all(t.annotations.readOnlyHint for t in listed.tools)

            async def call(name, args):
                result = await session.call_tool(name, args)
                if result.isError:
                    raise RuntimeError("MCP read failed; inspect safe diagnostics")
                return result.structuredContent

            catalog = await call("edstem_find_operations", {})
            assert len(catalog) == 27
            await call("edstem_describe_operation", {"operation": "threads"})
            raw = await call("edstem_read", {"operation": "user"})
            courses = [x["course"] for x in raw["data"]["courses"]]
            expected["course_count"] = len(courses)
            courses.sort(key=lambda c: c.get("status") != "active")
            chosen = None
            attachment_sources = []
            for course in courses:
                path = {"course_id": course["id"]}
                page = await call(
                    "edstem_read",
                    {
                        "operation": "threads",
                        "path": path,
                        "query": {"limit": 20},
                        "compact": False,
                    },
                )
                if chosen is None and page["data"]["threads"]:
                    thread = next(
                        (t for t in page["data"]["threads"] if t.get("reply_count", 0)),
                        page["data"]["threads"][0],
                    )
                    chosen = (course, thread)
                files = await call(
                    "edstem_list_attachments", {"operation": "resources", "path": path}
                )
                if files["attachments"]:
                    attachment_sources.append({"operation": "resources", "path": path})
                for row in page["data"]["threads"]:
                    if attachments(row):
                        attachment_sources.append(
                            {"operation": "thread", "path": {"thread_id": row["id"]}}
                        )
            if chosen is None:
                raise RuntimeError("No accessible thread available for semantic verification")
            course, before = chosen
            thread_id = before["id"]
            detail = await call(
                "edstem_read", {"operation": "thread", "path": {"thread_id": thread_id}}
            )
            t = detail["data"]["thread"]
            await call(
                "edstem_read",
                {
                    "operation": "course_thread",
                    "path": {"course_id": course["id"], "number": t["number"]},
                },
            )
            text = await call(
                "edstem_read_text", {"operation": "thread", "path": {"thread_id": thread_id}}
            )
            assert text["text"] and text["untrusted_content"]
            query_word = next((w for w in t["title"].split() if len(w) > 2), t["title"])
            matches = await call(
                "edstem_search_threads",
                {
                    "course_id": course["id"],
                    "text": query_word,
                    "limit": 20,
                    "include_replies": True,
                },
            )
            assert any(x["id"] == thread_id for x in matches["matches"])
            invalid = await session.call_tool(
                "edstem_read",
                {"operation": "thread", "path": {"thread_id": thread_id}, "query": {"view": 1}},
            )
            assert invalid.isError
            invalid_schema = await session.call_tool(
                "edstem_search_threads", {"course_id": "invalid", "text": "check"}
            )
            assert invalid_schema.isError
            expected.update(
                course_id=course["id"],
                course_name=course["name"],
                thread_id=t["id"],
                thread_number=t["number"],
                thread_title=t["title"],
                top_level_comments=len(t.get("comments", [])),
                top_level_answers=len(t.get("answers", [])),
                thread_text_sample=content_text(t),
            )
            summary.update(
                tools=len(listed.tools),
                operations=len(catalog),
                course_count=len(courses),
                search_match=True,
                rejected_tracking=True,
                rejected_bad_schema=True,
            )
            summary["attachment_extraction"] = "no_supported_sample"
            summary["image_read"] = "no_sample"
            for source in attachment_sources[:8]:
                listing = await call("edstem_list_attachments", source)
                for item in listing["attachments"][:3]:
                    params = source | {"index": item["index"]}
                    if summary["attachment_extraction"] != "verified":
                        result = await session.call_tool(
                            "edstem_read_attachment", params | {"max_chars": 2000}
                        )
                        if not result.isError and result.structuredContent.get("text", "").strip():
                            expected.update(
                                attachment_source=params,
                                attachment_text_sample=result.structuredContent["text"],
                            )
                            summary["attachment_extraction"] = "verified"
                    if summary["image_read"] != "verified":
                        result = await session.call_tool("edstem_read_image", params)
                        if not result.isError and any(c.type == "image" for c in result.content):
                            summary["image_read"] = "verified"
                if (
                    summary["attachment_extraction"] == "verified"
                    and summary["image_read"] == "verified"
                ):
                    break
            native = await call(
                "edstem_read",
                {
                    "operation": "native_search",
                    "path": {"course_id": course["id"]},
                    "query": {"query": query_word, "limit": 100},
                },
            )
            assert any(r["id"] == thread_id for r in native["data"]["threads"])
            empty = await call(
                "edstem_read",
                {
                    "operation": "native_search",
                    "path": {"course_id": course["id"]},
                    "query": {"query": "edstem_check_no_match_9e32b841c7"},
                },
            )
            assert not empty["data"]["threads"]
            summary["native_search"] = "verified_positive_and_negative"
            again = await call(
                "edstem_read",
                {
                    "operation": "threads",
                    "path": {"course_id": course["id"]},
                    "query": {"limit": 20},
                    "compact": False,
                },
            )
            after = next(x for x in again["data"]["threads"] if x["id"] == thread_id)
            state = ["is_seen", "glanced_at", "view_count", "unique_view_count"]
            summary["thread_state_unchanged"] = all(before.get(k) == after.get(k) for k in state)
            assert summary["thread_state_unchanged"]
    client = EdClient(Settings.load(ROOT / ".env"))
    try:
        direct_user = (await client.read("user"))["data"]
        assert len(direct_user["courses"]) == expected["course_count"]
        direct_course = next(
            x["course"]
            for x in direct_user["courses"]
            if x["course"]["id"] == expected["course_id"]
        )
        assert direct_course["name"] == expected["course_name"]
        direct = (await client.read("thread", {"thread_id": expected["thread_id"]}))["data"][
            "thread"
        ]
        assert direct["title"] == expected["thread_title"]
        assert direct["number"] == expected["thread_number"]
        assert len(direct.get("comments", [])) == expected["top_level_comments"]
        assert len(direct.get("answers", [])) == expected["top_level_answers"]
    finally:
        await client.close()
    log = ROOT / ".local/logs/edstem-mcp.jsonl"
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(r["operation"] == "thread" and r["code"] == "invalid_request" for r in records)
    (LOCAL / "live-expected.json").write_text(json.dumps(expected))
    (LOCAL / "live-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    os.umask(0o077)
    try:
        asyncio.run(main())
    except Exception as error:
        ErrorLog(LOCAL / "logs").record("live_verification_failure", error)
        raise SystemExit(
            "Live verification failed; no private response or exception was printed."
        ) from None
