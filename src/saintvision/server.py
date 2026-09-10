"""Production entrypoint. Demo fixtures live in saintvision.demo_server explicitly."""
from inv.app import create_configured_app


def create_app():
    return create_configured_app()
