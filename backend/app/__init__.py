"""ASR backend package.

Loads backend/.env before anything else is imported, so settings such as HF_HOME
are in place before Hugging Face reads them. Variables already set in the shell win.
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
