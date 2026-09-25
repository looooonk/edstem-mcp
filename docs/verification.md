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
