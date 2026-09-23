# Edstem MCP

Personal, local, read-only access to the US Ed Discussion API from Codex.
Python 3.12, uv, stdio transport. No hosted service or GitHub Actions.

## Setup

Keep your token in the ignored `.env` file as `ED_API_TOKEN=...`. Never paste it into Codex.

```sh
uv sync --locked
uv run python scripts/install_codex.py
```

The installer registers the absolute `.venv/bin/edstem-mcp` command in your persistent
Codex configuration, supplies only the `.env` path, and enables the local pre-commit hook.
Start a new Codex task to load the server. Codex starts it on demand after restarts;
no terminal, daemon, or launch agent needs to remain running. Keep this checkout and `.venv`
at their current locations, or rerun the installer after moving them.

## Tools

| Tool | Purpose |
| --- | --- |
| `edstem_find_operations` | Find named reads for a topic |
| `edstem_describe_operation` | Inspect exact parameters, limits, and evidence |
| `edstem_read` | Read structured Ed data and follow pagination |
| `edstem_read_text` | Extract readable post, reply, and lesson text in slices |
| `edstem_search_threads` | Bounded local keyword search, optionally including replies |
| `edstem_list_attachments` | Discover direct Ed CDN files in an accessible source |
| `edstem_read_attachment` | Extract attachment text without saving it |

Operations cover profile/enrollments, courses/categories, posts/announcements/replies,
user activity, resources, lessons/slides/questions/existing responses, attendance records,
and permission-limited analytics. Discover the exact catalog through the tools or
`edstem://operations`; workflow guidance is available at `edstem://guide`.

## Read-only boundaries

The HTTP client only accepts centrally allowlisted operations and parameters and only sends
GET requests to `https://us.edstem.org/api`. It rejects arbitrary routes, URLs, methods,
view flags, tracking parameters, and redirects. Tools cannot post, vote, mark read, subscribe,
check in, submit work, complete lessons, start assessments, or execute code.

Search uses local matching because an unofficial client's server search filter was silently
ignored. Follow `next_offset` to search further; a single page is never an exhaustive answer.
API list pagination uses `pagination.next_query`. Text slicing uses `next_offset` separately.
403 responses mean inaccessible, not empty. Lesson and attendance detail routes have source
evidence but may not have live records in this account.

Attachments are selected from a freshly read source by index; callers cannot supply a URL.
Only direct, unsigned `static.us.edusercontent.com` file links are fetched, with no token or
cookies. Limits are 25 MiB per file, 300 PDF pages, and 50 MiB expanded Office files.
Supported extraction: PDF, DOCX, PPTX, HTML, and UTF-8 text. No OCR, images, audio/video,
external websites, signed links, chat, notifications, or WebSocket subscriptions.

## Diagnostics and development

Automatic errors are stored in ignored `.local/logs/edstem-mcp.jsonl`, with three rotated
1 MiB backups and owner-only file permissions. Entries include timestamp, tool/operation,
error type, status, and source locations. They never contain arguments, exception messages,
credentials, URLs, headers, or response bodies. SDK logging is disabled to avoid raw validation
errors on stderr. If logging itself fails, stderr contains a fixed safe message.

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The pre-commit hook also rejects private artifacts and the current token in staged content.
Live checks are opt-in and keep private verification artifacts under `.local/`.
