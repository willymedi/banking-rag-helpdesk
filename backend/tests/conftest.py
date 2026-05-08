import os
import sys
from pathlib import Path

# Ensure src on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Disable network deps by default in unit tests
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8001")
