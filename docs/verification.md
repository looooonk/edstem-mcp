# Verification

## Offline checks

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests use fake tokens and mocked transports. They cover every catalog route, forbidden inputs
before network access, credentials and redirects, paging, schema drift, local search including
replies, attachment host restrictions, extraction, MCP annotations/output schemas, safe tool
errors, and private rotating logs. `.githooks/pre-commit` runs these checks and the secret guard.

## Live checks (explicit reads)

```sh
uv run python scripts/live_smoke.py
uv run python scripts/install_codex.py
uv run python scripts/verify_codex.py --model gpt-6-luna
```

`live_smoke.py` launches a fresh MCP process over stdio, discovers the tools, reads course/thread
data, validates text and search, rejects tracking flags and malformed schemas, and checks the
sampled thread's seen/glance state and view counters. It checks native search with both a known
match and a nonsense query. Where samples exist, it reads a PDF/text attachment and a native
PNG/JPEG image. It compares thread metadata against a direct API read independently of MCP.

`verify_codex.py` uses the existing ChatGPT subscription through `codex exec`, defaults to
GPT-6 Luna, and reconstructs the installed persistent Edstem command in an isolated invocation.
Shell, apps, and subagents are disabled. It checks tool-call events, eight exact fields
(course count, course/thread IDs, names/title, post number, comment and answer counts), and
verbatim thread/attachment excerpts against live reference values. Private responses and
events stay in `.local/` with owner-only permissions. Console output is limited to safe counts
and pass/fail metadata. The verification does not send the Ed token to the model.

The MCP command uses an absolute interpreter and `.env` path. Fresh stdio processes and a
separate Codex invocation verify startup independently of the active shell. Persistent user
configuration makes it available after restarting Codex or the computer; no actual computer
reboot is performed by these checks.

Results are recorded in ignored `.local/live-summary.json` and `.local/codex-summary.json`.
Operation-specific live coverage and limitations are documented in [operations.md](operations.md).
Do not mistake source-reviewed endpoints for successful live tests of unavailable records.

## Diagnostic isolation

Both verification scripts pass `--log-dir .local/verification/logs` as an absolute
path to the MCP process. Deliberately invalid requests and live verification errors
stay there; normal Codex sessions continue to use `.local/logs/`. Historical logs
are not rewritten. Run the Codex check with `--model gpt-6-luna`.

The September 25, 2026 fresh GPT-6 Luna check passed with 15 MCP calls,
using the command registered in Codex. Offline checks passed with
88 tests. Operational log contents remained unchanged throughout verification.
Attachment reference selection requires readable text beyond PDF page labels, so scanned
PDFs with no extracted body text cannot count as successful quotation samples.

## Version 0.2.0 validation, October 30, 2026

Ruff check and format checks passed; the offline synthetic suite passed 102 tests.
New tests cover baseline/resume/replay, change pagination, scope/role/expiry isolation,
partial failure retention, deadline updates, noise normalization and read-only boundaries.
An explicit bounded live baseline/resume read succeeded; full course reconciliation is
covered synthetically, including changed replies on old threads with unchanged post order.
Deployment and Mac session results are reported separately; these test results alone
do not establish a deployed cloud version or a physical Mac-off test.

## Version 0.2.1 review

The shared schema-2 feed preserves nested content fields and array order, strips
only known URL authentication parameters, reports pagination cycles as partial,
counts failed tasks toward scan limits, closes SQLite connections, and bounds
cached responses as well as inserts. Regression tests cover content reorder,
semantic URL versions, partial-page recovery, failed-task limits and reply size.
`ruff check`, `ruff format --check` and all 105 tests passed on Python 3.12.
No campus mutation probes were used.

## Version 0.2.2 compatibility

All 122 tests, ruff checks and formatting checks pass. The existing find/describe/read
input schemas are compared against the prior installed release. Synthetic tests verify
wrapper/dedicated cursor interoperability, event pagination and replay, role isolation,
partial coverage, rejection of projection/pagination conflicts, malformed nested options
before reads, and rejection of this local operation by upstream HTTP clients.
Feed errors now retain their safe actionable message through tool error handling.
