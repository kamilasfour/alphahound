"""Quick global markets check — run anytime to see overnight Asian/European action.

Usage:
    .\.venv\Scripts\python.exe scripts\global_markets.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.global_markets import fetch_global_markets, print_summary

print("Fetching global markets data...")
summary = fetch_global_markets()
print_summary(summary)
