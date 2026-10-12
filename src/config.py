import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Read simple KEY=value entries without echoing values or requiring a dotenv package.
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
DB_PATH = Path(os.getenv("AUTOARCH_DB_PATH", ROOT / "data" / "autoarch.db"))
MAX_UPLOAD_MB = int(os.getenv("AUTOARCH_MAX_UPLOAD_MB", "30"))
TOP_K = int(os.getenv("AUTOARCH_TOP_K", "5"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    try:
        import streamlit as st
        OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
        OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", OPENAI_MODEL)
    except Exception:
        # Streamlit secrets are optional for local tests and non-Streamlit imports.
        pass
