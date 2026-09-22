"""Model import adapter: exact comparison of an import proposal against the immutable manifest.

VF-CL-03 (Codex verdict, relayed 2026-09-22): the kernel's ``ModelManifest`` is the
immutable declaration of ``licensePolicy`` and ``classification``. An import proposal
(what an importer *claims* it is bringing in) must match that declaration **exactly** --
byte-for-byte string equality, no case folding, no whitespace trimming, no prefix or
wildcard matching -- and any mismatch is a refusal (fail-closed). A missing field is a
mismatch. An extra, unknown field in the proposal is a mismatch too: a proposal cannot
carry values the declaration does not have.

What a match does NOT mean: it is not a legal licence permission and it is not an execution
approval. Admission to run is decided elsewhere (deployment admission against the operator's
registry binding policy, ``inv.model_registry_binding``); this adapter only establishes that
the importer's claim and the immutable declaration are the same values.

Claude-owned adapter; the contract is unchanged and the kernel is not touched.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..errors import InvError

#: The declaration fields this adapter compares. Order is part of the report, not of the
#: comparison (every field must match).
DECLARED_FIELDS: tuple[str, ...] = ("licensePolicy", "classification")

MODEL_IMPORT_DECLARATION_MISMATCH = "VAL-MODEL-IMPORT-DECLARATION"


def declaration_mismatch(mismatches: list[str]) -> InvError:
    """The refusal for a proposal that does not equal the immutable declaration.

    ``extra["mismatches"]`` names the fields (never their values, which may be operator
    text) so the refusal is diagnosable without echoing the proposal. ``InvError`` is a
    slotted dataclass, so this is a factory rather than a subclass.
    """
    reasons = list(mismatches)
    return InvError(
        MODEL_IMPORT_DECLARATION_MISMATCH,
        "import proposal differs from the immutable manifest declaration: " + ", ".join(reasons),
        status=409,
        public=True,
        extra={"mismatches": reasons},
    )


def compare_declaration(manifest: Mapping[str, Any], proposal: Mapping[str, Any]) -> list[str]:
    """Return the list of mismatching field names (empty means an exact match).

    Pure and side-effect free. Rules, each one a separate reason string:

    * ``missing:<field>``  -- the proposal lacks a declared field.
    * ``differs:<field>``  -- present but not ``==`` to the declaration (strings compare
      exactly; ``"internal"`` != ``"Internal"`` != ``" internal"``; a non-string is never
      equal to the declared string).
    * ``extra:<field>``    -- the proposal carries a field outside ``DECLARED_FIELDS``.
    * ``undeclared:<field>`` -- the manifest itself lacks a declared field; a declaration
      that is not complete cannot be matched, so this is a refusal, not a pass.
    """
    reasons: list[str] = []
    for field in DECLARED_FIELDS:
        if field not in manifest or not isinstance(manifest[field], str):
            reasons.append(f"undeclared:{field}")
            continue
        if field not in proposal:
            reasons.append(f"missing:{field}")
            continue
        value = proposal[field]
        if not isinstance(value, str) or value != manifest[field]:
            reasons.append(f"differs:{field}")
    for field in proposal:
        if field not in DECLARED_FIELDS:
            reasons.append(f"extra:{field}")
    return reasons


def require_exact_declaration(manifest: Mapping[str, Any], proposal: Mapping[str, Any]) -> None:
    """Fail-closed gate: raise the mismatch ``InvError`` unless the proposal equals the
    declaration exactly. Returning normally means "same values", nothing more."""
    reasons = compare_declaration(manifest, proposal)
    if reasons:
        raise declaration_mismatch(reasons)
