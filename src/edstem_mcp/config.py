import ssl
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

BASE_URL = "https://us.edstem.org/api"
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)

    def __post_init__(self):
        if not self.token or not self.token.isascii() or any(c.isspace() for c in self.token):
            raise ValueError("ED_API_TOKEN is missing or invalid in the local .env file.")

    @classmethod
    def load(cls, env_file: Path):
        return cls(dotenv_values(env_file, interpolate=False).get("ED_API_TOKEN") or "")


def tls_context() -> ssl.SSLContext:
    # uv's Python may not discover the macOS certificate bundle automatically.
    bundle = Path("/etc/ssl/cert.pem")
    return ssl.create_default_context(cafile=str(bundle) if bundle.is_file() else None)
