"""ADR-075 internal boundary, never authority supplied by a browser.

The caller constructs CredentialContext only from verified authentication and
current execution scope. Implementations must additionally verify registry and
current grants at resolution and immediately before dispatch. This module is a
protocol, not an implementation of those security checks.
"""

from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

CONTRACT_VERSION = "1.0.0"
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CredentialContext:
    tenant_id: str
    project_id: str
    subject_id: str
    run_id: str


class CredentialDenied(Exception):
    """Fixed public error, with no locator, secret or provider exception text."""

    def __init__(self):
        super().__init__("Credential unavailable for this operation")


class CredentialHandle(Protocol):
    def use(self, callback: Callable[[bytes], T]) -> T:
        """Recheck authority then call once; never retry an ambiguous callback.

        Callback is trusted adapter code, not user code. Raw secret bytes must
        not be retained, returned or logged by that adapter. This interface
        cannot enforce erasure of Python memory or retract external effects.
        """
        ...


class CredentialResolver(Protocol):
    def resolve(
        self,
        reference: str,
        authenticated_context: CredentialContext,
        purpose: str,
        destination_alias: str,
    ) -> CredentialHandle:
        """Return a version-pinned handle, or raise CredentialDenied safely."""
        ...
