"""Shared pytest configuration.

Nothing DB-touching here — we keep Sprint 2 tests pure-unit (no network,
no DB) so `pytest -q` runs in under a second on any machine.
"""
