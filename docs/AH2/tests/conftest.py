"""Pytest configuration: make the AH2 Functions app source importable.

src/ is the Azure Functions deployment unit and is not an installed
package, so tests need src/ on sys.path to import function_app,
domain.*, application.*, infrastructure.*, and shared.* directly —
matching how the Functions host itself imports them at runtime.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
