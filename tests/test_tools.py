import json

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from edstem_mcp.catalog import EdError
from edstem_mcp.client import EdClient
from edstem_mcp.config import Settings
from edstem_mcp.content import extract_text, html_text, text_slice
from edstem_mcp.diagnostics import ErrorLog
from edstem_mcp.files import attachments, read_attachment, safe_url
from edstem_mcp.search import search_threads
from edstem_mcp.server import create_server


@pytest.mark.parametrize(
    "url",
    [
        "http://static.us.edusercontent.com/files/x.txt",
        "https://static.us.edusercontent.com.evil.test/files/x.txt",
        "https://static.us.edusercontent.com@evil.test/files/x.txt",
        "https://127.0.0.1/files/x.txt",
        "https://us.edstem.org/api/user",
        "https://static.us.edusercontent.com/api/user",
        "https://static.us.edusercontent.com/files/../api/user",
        "https://static.us.edusercontent.com/files/%2e%2e/api/user",
        "https://static.us.edusercontent.com/files/x?view=1",
        "https://static.us.edusercontent.com:443/files/x",
    ],
)
def test_unsafe_downloads(url):
    assert not safe_url(url)


def test_extract_attachments_from_ed_xml():
    url = "https://static.us.edusercontent.com/files/abc.pdf"
    data = {
        "thread": {
            "content": f'<document><file url="{url}">notes.pdf</file></document>',
            "comments": [{"content": '<link href="https://evil.test/secret">x</link>'}],
        }
    }
    assert attachments(data) == [{"index": 0, "url": url, "name": "notes.pdf"}]


async def test_attachment_no_credentials_and_no_disk(tmp_path):
    token = "private-credential"
    url = "https://static.us.edusercontent.com/files/abc.txt"
    client = EdClient(
        Settings(token),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"thread": {"content": f'<file url="{url}"/>'}}
            )
        ),
    )

    def download(request):
        assert request.method == "GET"
        assert "authorization" not in request.headers and "cookie" not in request.headers
        return httpx.Response(200, text="hello world", headers={"content-type": "text/plain"})

    result = await read_attachment(
        client, "thread", {"thread_id": 1}, 0, max_chars=5, transport=httpx.MockTransport(download)
    )
    assert result["text"] == "hello" and result["next_offset"] == 5
    assert not list(tmp_path.iterdir())
    await client.close()


async def test_attachment_redirect_is_blocked():
    url = "https://static.us.edusercontent.com/files/abc.txt"
    client = EdClient(
        Settings("token"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"resources": [{"url": url}]})
        ),
    )
    requests = []

    def download(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://evil.test/"})

    with pytest.raises(EdError, match="redirects"):
        await read_attachment(
            client, "resources", {"course_id": 1}, 0, transport=httpx.MockTransport(download)
        )
    assert len(requests) == 1
    await client.close()


async def test_search_matches_reply_and_has_resume():
    def respond(request):
        assert "filter" not in request.url.params and "view" not in request.url.params
        if request.url.path.endswith("/threads"):
            return httpx.Response(200, json={"threads": [{"id": 2, "title": "Weekly notes"}]})
        return httpx.Response(
            200,
            json={
                "thread": {
                    "id": 2,
                    "number": 3,
                    "title": "Weekly notes",
                    "comments": [{"content": "<paragraph>Exam Friday</paragraph>"}],
                }
            },
        )

    client = EdClient(Settings("token"), transport=httpx.MockTransport(respond))
    result = await search_threads(client, 1, "exam friday", limit=1, include_replies=True)
    assert result["matches"][0]["id"] == 2
    assert result["next_offset"] == 1 and not result["reached_end"]
    miss = await search_threads(client, 1, "nonsense", limit=2)
    assert miss["matches"] == [] and miss["reached_end"]
    await client.close()


async def test_tools_annotations_safe_errors_and_logging(tmp_path):
    client = EdClient(
        Settings("secret-token"),
        transport=httpx.MockTransport(lambda request: httpx.Response(403, text="private body")),
    )
    server = create_server(Settings("secret-token"), tmp_path, client=client)
    tools = await server.list_tools()
    assert len(tools) == 8
    assert all(t.outputSchema is not None for t in tools if t.name != "edstem_read_image")
    assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in tools)
    for name, args in [
        ("edstem_read", {"operation": "user"}),
        ("edstem_read", {"operation": "private argument"}),
        ("edstem_read", {"operation": "user", "path": "private argument"}),
        ("private tool", {}),
    ]:
        with pytest.raises(ToolError) as error:
            await server.call_tool(name, args)
        assert "private argument" not in str(error.value)
    logs = (tmp_path / "edstem-mcp.jsonl").read_text()
    assert all(
        x not in logs for x in ["secret-token", "private body", "private argument", "private tool"]
    )
    records = [json.loads(line) for line in logs.splitlines()]
    assert len(records) == 4
    assert records[0]["http_status"] == 403
    assert (tmp_path / "edstem-mcp.jsonl").stat().st_mode & 0o777 == 0o600
    await client.close()


def test_log_rotation(tmp_path):
    log = ErrorLog(tmp_path, max_bytes=1, backups=2)
    for _ in range(4):
        log.record("tool_failure", ValueError("must not appear"))
    assert len(list(tmp_path.glob("*.jsonl*"))) == 3
    assert all("must not appear" not in p.read_text() for p in tmp_path.glob("*.jsonl*"))


def test_text_extraction_and_pagination():
    assert "secret" not in html_text("<script>secret</script><paragraph>hello</paragraph>")
    assert extract_text(b"hello", "x.txt", "text/plain")[0] == "hello"
    assert text_slice("abcdef", 2, 2) == {
        "text": "cd",
        "offset": 2,
        "total_chars": 6,
        "next_offset": 4,
    }
    with pytest.raises(EdError):
        extract_text(b"binary", "x.exe", "application/octet-stream")
