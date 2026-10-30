from edstem_mcp.changefeed import ChangeFeed
from edstem_mcp.changes import EdChanges


class Client:
    def __init__(self):
        self.reply = "first"
        self.calls = []
        self.views = 1

    async def read(self, name, path=None, query=None):
        self.calls.append((name, path, query))
        if name == "user":
            return {"data": {"courses": [{"course": {"id": 1}, "role": {"role": "student"}}]}}
        if name == "threads":
            return {
                "data": {"threads": [{"id": 2, "number": 1}]},
                "pagination": {"next_query": None},
            }
        return {
            "data": {
                "thread": {
                    "id": 2,
                    "course_id": 1,
                    "number": 1,
                    "title": "Old post",
                    "views": self.views,
                    "comments": [{"id": 3, "content": self.reply, "comments": []}],
                }
            }
        }


async def test_old_thread_replies_reconciled_and_views_ignored(tmp_path):
    client = Client()
    feed = ChangeFeed(tmp_path, "account", EdChanges())
    baseline = await feed.read(client, "1")
    client.views = 100
    unchanged = await feed.read(client, "1", cursor=baseline["next_cursor"])
    assert unchanged["changes"] == []
    client.reply = "edited answer"
    changed = await feed.read(client, "1", cursor=unchanged["next_cursor"])
    assert len(changed["changes"]) == 1
    assert changed["changes"][0]["resource_type"] == "reply"
    assert all("view" not in (q or {}) for _, _, q in client.calls)
    assert sum(name == "thread" for name, _, _ in client.calls) == 3
