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
| `edstem_read_image` | Show PNG/JPEG attachments to Codex |

Operations cover profile/enrollments, courses/categories, posts/announcements/replies,
user activity, resources, lessons/slides/questions/existing responses, attendance records,
lab/tutorial groups, saved snippets, and permission-limited analytics. There are 27 named
API operations behind these eight tools. Discover the exact catalog through the tools or
`edstem://operations`; workflow guidance is available at `edstem://guide`.

## Read-only boundaries

The HTTP client only accepts centrally allowlisted operations and parameters and only sends
GET requests to `https://us.edstem.org/api`. It rejects arbitrary routes, URLs, methods,
view flags, tracking parameters, and redirects. Tools cannot post, vote, mark read, subscribe,
check in, submit work, complete lessons, start assessments, or execute code.

Use `native_search` with `query={"query": "keywords"}` for Ed's current indexed search.
The separate `edstem_search_threads` tool provides local matching with optional reply scanning.
An unofficial client's `filter=search:...` approach was silently ignored and is not used.
Follow `next_offset` to search further locally; a single page is never an exhaustive answer.
API list pagination uses `pagination.next_query`. Text slicing uses `next_offset` separately.
403 responses mean inaccessible, not empty. Lesson and attendance detail routes have source
evidence but may not have live records in this account.

Attachments are selected from a freshly read source by index; callers cannot supply a URL.
Only direct, unsigned `static.us.edusercontent.com` file links are fetched, with no token or
cookies. Limits are 25 MiB per file, 300 PDF pages, and 50 MiB expanded Office files.
Supported extraction: PDF, DOCX, PPTX, HTML, and UTF-8 text. Parsing is isolated in a child
process with CPU/time limits. PNG/JPEG attachments up to 5 MiB can be returned as native MCP
images. No PDF OCR, audio/video, external websites, signed links, chat, notifications, or
WebSocket subscriptions. Dedicated resource-download routes returned 404 with this token;
resource metadata and direct embedded attachments are available.
Default profile responses summarize all memberships and include explicit list counts;
use `compact=false` when full settings are needed.

Examples to ask Codex:

- "Find announcements about the exam in my current Ed courses."
- "Read post #42 and its replies in this course."
- "Search for deadline extensions, and show the source posts."
- "Read the PDF attached to this post" or "Show me its image attachment."

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

See [endpoint evidence](docs/operations.md), [security boundaries](docs/security.md), and
[live Codex verification](docs/verification.md). To rerun the checks:

```sh
make live
make verify
```

If startup fails, run `uv sync --locked` and rerun the installer. If authentication fails,
replace the token locally in `.env` and start a new Codex task. Do not paste the token into
a task or log. To remove the integration, run `codex mcp remove edstem`; the repository remains.
