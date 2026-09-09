"""Minimal non-operational service shell. Business APIs are handed to Claude."""

from fastapi import FastAPI
from . import __version__

app = FastAPI(title="Saint Vision INV Control Plane", version=__version__)


@app.get("/healthz")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/readyz", status_code=503)
def ready():
    return {
        "status": "not_ready",
        "reason": "node-runtime-and-identity-integration-pending",
    }


def main():
    import uvicorn

    uvicorn.run("inv.app:app", host="127.0.0.1", port=8080)
