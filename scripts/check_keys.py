"""Sanity check — confirms all Sprint 5 API keys are loaded from .env."""
from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from project root (two levels up from scripts/)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

keys = [
    "FINNHUB_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "MASSIVE_API_KEY",
    "QUIVER_API_KEY",
    "UNUSUAL_WHALES_API_KEY",
]

all_ok = True
for name in keys:
    val = os.getenv(name)
    if val:
        print(f"  OK  {name} ({len(val)} chars)")
    else:
        print(f"  MISSING  {name}")
        all_ok = False

print()
print("All keys loaded." if all_ok else "Some keys are missing — check your .env file.")
