from edstem_mcp.catalog import EdError
from edstem_mcp.changefeed import FeedError, record, selected


class EdChanges:
    errors = (EdError, FeedError)
    coverage = (
        "All visible course threads, including full answers/comments on old threads on every scan."
    )

    async def authorize(self, client, course):
        data = (await client.read("user"))["data"]
        membership = next(
            (item for item in data["courses"] if str(item.get("course", {}).get("id")) == course),
            None,
        )
        if membership is None:
            raise FeedError("Course is not in your current Ed memberships.")
        return membership.get("role", {}).get("role", "unknown")

    def tasks(self, course, role):
        return [{"source": "threads", "offset": 0}]

    async def collect(self, client, course, task):
        if task["source"] == "threads":
            result = await client.read(
                "threads",
                {"course_id": course},
                {"limit": 50, "offset": task["offset"], "sort": "new"},
            )
            tasks = []
            for row in result["data"]["threads"]:
                if not isinstance(row, dict) or row.get("id") is None:
                    raise FeedError("Ed thread listing is missing a stable identifier.")
                tasks.append({"source": "thread", "id": row["id"]})
            next_query = result["pagination"]["next_query"]
            if next_query:
                tasks.append({"source": "threads", "offset": next_query["offset"]})
            return [], tasks
        thread = (await client.read("thread", {"thread_id": task["id"]}))["data"]["thread"]
        if str(thread.get("course_id")) != course or str(thread.get("id")) != str(task["id"]):
            raise FeedError("Thread identity or course does not match the discovered thread.")
        url = f"https://edstem.org/us/courses/{course}/discussion/{thread.get('number', '')}"
        keys = (
            "title type category subcategory subsubcategory content document "
            "is_answered is_resolved is_pinned is_locked is_private "
            "is_anonymous"
        )
        records = [record("thread", thread["id"], thread.get("title"), url, selected(thread, keys))]
        stack = [(thread, str(thread["id"]))]
        while stack:
            node, parent = stack.pop()
            for key in ("answers", "comments"):
                children = node.get(key, [])
                if not isinstance(children, list):
                    raise FeedError("Ed replies have an unexpected shape; scan is incomplete.")
                for reply in children:
                    if not isinstance(reply, dict) or reply.get("id") is None:
                        raise FeedError("Ed reply is missing a stable identifier.")
                    identifier = str(reply["id"])
                    values = selected(
                        reply, "content document is_endorsed is_anonymous is_private is_resolved"
                    )
                    values["parent_id"] = parent
                    values["reply_type"] = key
                    records.append(
                        record(
                            "reply",
                            f"{thread['id']}:{identifier}",
                            f"Reply on {thread.get('title', 'thread')}",
                            url,
                            values,
                        )
                    )
                    stack.append((reply, identifier))
                    if len(records) > 20000:
                        raise FeedError("Thread exceeds the reply limit.")
        return records, []
