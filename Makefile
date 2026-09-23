.PHONY: setup install check test live verify serve
setup:
	uv sync --locked
install: setup
	uv run --locked python scripts/install_codex.py
check:
	./scripts/check.sh
test:
	uv run --locked pytest
live:
	uv run --locked python scripts/live_smoke.py
verify:
	uv run --locked python scripts/verify_codex.py --model gpt-6-luna
serve:
	uv run --locked edstem-mcp
