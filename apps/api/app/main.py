"""Deploy entrypoint (`uvicorn app.main:app`) — an alias for the one app in main.py.

There used to be two divergent FastAPI apps (Trap #1): tests imported root
main.py while Railway ran this file, so a router mounted in only one passed CI
and silently did not exist in production. The single definition now lives in
main.py; this module only keeps the deploy path stable.
"""
from main import app

__all__ = ["app"]
