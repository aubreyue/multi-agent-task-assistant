from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
OUTPUTS_DIR = BASE_DIR / "outputs"
RUNS_DIR = OUTPUTS_DIR / "runs"
DOCS_DIR = BASE_DIR / "docs"
STATE_DIR = BASE_DIR / "state"
MEMORY_VECTORSTORE_DIR = STATE_DIR / "memory_vectorstore"
RUNTIME_DB_PATH = STATE_DIR / "runtime.db"


@dataclass
class Settings:
    openai_api_key: str
    openai_base_url: str
    chat_model: str
    embedding_model: str


def ensure_directories() -> None:
    for path in (DATA_DIR, VECTORSTORE_DIR, OUTPUTS_DIR, RUNS_DIR, DOCS_DIR, STATE_DIR, MEMORY_VECTORSTORE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
    )
