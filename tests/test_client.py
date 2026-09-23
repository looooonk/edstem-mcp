import httpx
import pytest

from edstem_mcp.catalog import OPERATIONS, EdError, describe, prepare
from edstem_mcp.client import EdClient
from edstem_mcp.config import BASE_URL, Settings


@pytest.mark.parametrize("name", OPERATIONS)
def test_catalog_read_only(name):
    spec = describe(name)
    path = dict.fromkeys(spec["path_parameters"], 123)
    params = {k: "example" for k, v in spec["query"].items() if v.get("required")}
    endpoint, query = prepare(name, path, params)
    assert endpoint.startswith("/") and "view" not in query
    assert spec["method"] == "GET"


@pytest.mark.parametrize(
    "name,path,query",
    [
        ("post_thread", {}, {}),
        ("/user", {}, {}),
        ("thread", {"thread_id": "1/../2"}, {}),
        ("thread", {"thread_id": "https://evil.test"}, {}),
        ("thread", {"thread_id": True}, {}),
        ("thread", {"thread_id": 0}, {}),
        ("thread", {"thread_id": 1, "other": 2}, {}),
        ("thread", {"thread_id": 1}, {"view": 1}),
        ("threads", {"course_id": 1}, {"filter": "search:test"}),
        ("threads", {"course_id": 1}, {"limit": True}),
        ("threads", {"course_id": 1}, {"limit": 101}),
        ("threads", {"course_id": 1}, {"offset": -1}),
        ("threads", {"course_id": 1}, {"sort": "delete"}),
        ("user", {}, {"url": "https://evil.test"}),
    ],
)
async def test_rejected_before_network(name, path, query):
    def reject(request):
        pytest.fail("Invalid requests must not reach the network")

    client = EdClient(Settings("fake-token"), transport=httpx.MockTransport(reject))
    with pytest.raises(EdError):
        await client.read(name, path, query)
    await client.close()


async def test_fixed_destination_get_and_pagination():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"threads": [{"id": 1}]})

    client = EdClient(Settings("fake-token"), transport=httpx.MockTransport(respond))
    result = await client.read("threads", {"course_id": 2}, {"limit": 1})
    assert result["pagination"]["next_query"] == {"limit": 1, "offset": 1, "sort": "new"}
    assert requests[0].method == "GET"
    assert str(requests[0].url).startswith(BASE_URL + "/courses/2/threads?")
    assert requests[0].headers["authorization"] == "Bearer fake-token"
    await client.close()


@pytest.mark.parametrize("status", [301, 302, 307, 400, 401, 403, 404, 429])
async def test_http_errors_safe_and_no_redirects(status):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status, text="private content", headers={"location": "https://evil.test"}
        )

    client = EdClient(Settings("fake-token"), transport=httpx.MockTransport(respond))
    with pytest.raises(EdError) as error:
        await client.read("user")
    assert error.value.http_status == status and "private" not in str(error.value)
    assert len(requests) == 1
    await client.close()


@pytest.mark.parametrize("body", [{}, {"threads": None}, {"threads": "secret"}])
async def test_collection_drift_is_not_empty_success(body):
    client = EdClient(
        Settings("fake-token"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    with pytest.raises(EdError, match="shape"):
        await client.read("threads", {"course_id": 1})
    await client.close()


def test_config_hides_token(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ED_API_TOKEN=fake-token\n")
    assert "fake-token" not in repr(Settings.load(env))
