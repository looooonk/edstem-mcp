# Read-only and privacy design

## Enforced boundaries

The token is read directly from the local `.env` by the server. It is excluded from settings
representations, tool schemas, Codex configuration, logs, and Git. The server is fixed to the
US Ed origin. The model cannot choose an HTTP method, host, route, token, or arbitrary query.
All public tool inputs pass the same catalog validation before any API request is sent.

The HTTP client sends only GET, rejects redirects, verifies TLS, ignores proxy environment
variables, bounds response sizes, limits concurrency, and uses short timeouts. MCP tool calls have a 55-second overall limit. It retries a
temporary gateway error once, but does not retry rate limits or permission failures.
View flags are omitted for posts, lessons and slides. No POST/PUT/PATCH/DELETE, WebSocket
message, read receipt, presence subscription, or execution operation exists in the server.

MCP read-only annotations describe this behavior; the catalog and HTTP code enforce it.
Mock tests assert that rejected requests reach no network handler. Live checks compare
sampled seen/glance state and view counters before and after reads. Ed can still keep ordinary
server access logs, and its private API can change; these checks are not a backend guarantee.

## Attachments

The model supplies an Ed source operation/path and an attachment index. The server reloads
that source and derives the URL itself. It only accepts HTTPS on the exact
`static.us.edusercontent.com` host with `/files/` or `/uploads/` paths, rejecting credentials,
ports, query strings, fragments, traversal and redirects. External and signed URLs are omitted.
A separate HTTP client gets no Ed token or cookies.

Files are bounded at 25 MiB. Text parsing runs in a separate process with a 15-second CPU
limit, a 25-second wall-clock timeout, no inherited credential environment, a 300-page PDF
limit, 50 MiB expanded Office limit, and a two-million-character output limit. XML external
entities are disabled. Files and extracted content are not saved by the server. Native PNG/JPEG
image results are capped at 5 MiB; these do not execute the embedded content.

## Errors

Tool errors, invalid arguments, resource errors, and startup/runtime failures are automatically
logged under `.local/logs/`. Log rotation is protected by a process lock. Files are owner-only;
the normal entrypoint uses umask 077. Logged fields are limited to time, event, PID, known tool
and operation names, error type/code, HTTP status, and source locations. Nested exception
groups are unwrapped without their messages. No arguments, token, URL, body, exception message,
or local variable is included. Raw SDK/library logging is disabled by the entrypoint.

Invalid arguments are converted to fixed safe MCP errors so schema validation cannot echo
private inputs. OS-level termination or power loss cannot reliably produce a final log entry.
If log storage itself fails, the process prints only a fixed diagnostic message to stderr.

## Local trust

This is not a security boundary against other processes running as the same macOS user.
They can read this user's `.env` and Codex history. Ed content and attachments are untrusted
data; the MCP instructions explicitly prohibit treating them as instructions. Private live
verification artifacts and Codex configuration backups are ignored under `.local/`.
Do not publish that directory. The pre-commit hook checks staged paths and scans staged
content for the current token without displaying it.
