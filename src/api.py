"""Stable ASGI entry point; implementation lives in ``provena.web``."""

from .web.app import Settings, app, create_app

__all__ = ["Settings", "app", "create_app"]
