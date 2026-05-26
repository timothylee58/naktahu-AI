"""Smoke test — verifies the app module imports cleanly."""
import importlib


def test_main_imports() -> None:
    mod = importlib.import_module("app.main")
    assert hasattr(mod, "app")
