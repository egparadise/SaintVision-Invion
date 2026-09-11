"""Agent adapter status: what is installed, signed in, and drivable.

Read-only. Nothing here installs a tool, signs anyone in, or starts a session,
and that is a deliberate boundary rather than an unfinished one: a Run has no
human in front of it, so a login flow would block until it timed out, and
fetching software during a request is a change to somebody's workstation that
nobody reviewed.

The screens Gemini builds poll this. Three consequences shaped it:

**One call per tool, not three.** "Is it installed", "which version" and "is it
signed in" are always asked together, and answering them separately means three
subprocess launches per tool per refresh.

**A tool that cannot answer says ``unknown``.** The tempting alternative is to
send a trivial prompt and infer login from whether it errors — which bills the
user every time a status screen refreshes.

**Installed-but-not-on-PATH is its own answer.** It looks identical to "not
installed" to anything that only checks ``which``, and it needs the opposite
advice.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...adapters import agents
from ...identity.principal import Principal
from ..deps import get_principal

router = APIRouter(prefix="/v1", tags=["adapters"])


@router.get("/adapters")
def list_adapters(principal: Principal = Depends(get_principal)) -> dict:
    """Install and login state for every agent CLI this platform knows about.

    Ordered, so a status screen does not reshuffle between refreshes. One tool
    failing is reported as that tool's state rather than failing the request —
    a screen showing three answers and a problem beats a screen showing nothing.
    """
    rows = agents.readiness()
    return {
        "adapters": rows,
        "measurementScope": "control-plane-host",
        "remoteNodeReadiness": "unknown",
        "readyCount": sum(
            1
            for row in rows
            if row.get("installed")
            and row.get("headless")
            and row.get("loginState") == "logged_in"
        ),
        # Said once, here, rather than implied by the absence of a button.
        "note": (
            "Status is observed, never changed. Installing a tool and signing "
            "in are things a person does on the machine; the platform reports "
            "what it finds."
        ),
    }


@router.get("/adapters/{name}")
def read_adapter(name: str, principal: Principal = Depends(get_principal)) -> dict:
    try:
        adapter = agents.adapter_for(name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"unknown adapter: {name}",
        ) from None
    probe = adapter.probe()
    return {
        **adapter.readiness(),
        "reachable": probe.reachable,
        "latencyMs": probe.latency_ms,
    }
