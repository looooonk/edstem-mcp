"""Reject private artifacts or the current token in staged content."""

import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = (
        subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    token = dotenv_values(ROOT / ".env", interpolate=False).get("ED_API_TOKEN")
    for name in filter(None, paths):
        path = Path(name)
        if any(p in {".local", ".venv"} for p in path.parts) or (
            path.name.startswith(".env") and path.name != ".env.example"
        ):
            raise SystemExit("Commit blocked: a private local artifact is staged.")
        if token and len(token) >= 8:
            content = subprocess.check_output(["git", "show", f":{name}"], cwd=ROOT)
            if token.encode() in content:
                raise SystemExit("Commit blocked: the Ed token occurs in staged content.")


if __name__ == "__main__":
    main()
