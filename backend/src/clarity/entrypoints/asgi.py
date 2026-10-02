"""ASGI entry point: ``uvicorn clarity.entrypoints.asgi:app``.

The top of the layer stack. Building the application here, and not at import of
the HTTP module, keeps the interface layer free of process-wide side effects and
lets tests and other entry points assemble their own instance.
"""

from __future__ import annotations

from clarity.interfaces.http.main import create_app

app = create_app()
