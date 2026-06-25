"""Central config: loads .env and exposes required keys. Fails loud if any key is missing."""
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env into the process environment


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(
            f"{key} is not set. Copy .env.example to .env and fill in your keys."
        )
    return value


ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _require("OPENAI_API_KEY")
GITHUB_TOKEN = _require("GITHUB_TOKEN")

EMBEDDING_MODEL = "text-embedding-3-small"
