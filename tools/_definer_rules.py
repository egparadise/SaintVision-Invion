"""How a SECURITY DEFINER function's source is judged.

Split out from ``check_definer_functions`` so the rules can be tested against
crafted definitions without a database — which is how the first version of each
rule here was found to be defeated by something that changed nothing about the
leak it was supposed to catch.
"""

from __future__ import annotations

import re

#: ``--`` to end of line and ``/* */`` blocks.
_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
#: A single-quoted SQL literal, in which '' is an escaped quote.
_LITERAL = re.compile(r"'(?:[^']|'')*'", re.DOTALL)
#: The masked form: a literal becomes \x00<index>\x00, which no SQL can contain.
_MASKED = "\x00{}\x00"


def mask_literals(body: str) -> tuple[str, list[str]]:
    """Strip comments and replace each string literal with a positional mask.

    Deleting literals outright was the obvious move and it was wrong in both
    directions. ``current_setting('inv.tenant_id')`` *is* a literal, so deleting
    literals erases the proof that a function binds its scope; leaving them
    erases the difference between calling it and merely mentioning it in a
    string. Masking keeps both distinctions: the call site survives as
    ``current_setting(<mask>)`` and the mask's contents are checked separately.
    """
    body = _COMMENT_BLOCK.sub(" ", body)
    body = _COMMENT_LINE.sub(" ", body)

    literals: list[str] = []

    def take(match: re.Match[str]) -> str:
        raw = match.group(0)[1:-1].replace("''", "'")
        literals.append(raw)
        return _MASKED.format(len(literals) - 1)

    return _LITERAL.sub(take, body), literals


#: ``current_setting(`` immediately followed by a masked literal.
_SETTING_CALL = re.compile(r"current_setting\s*\(\s*\x00(\d+)\x00")


def binds_tenant_scope(body: str) -> bool:
    """Does the body actually call ``current_setting('inv.tenant_id')``?

    A comment promising the binding and a string literal quoting it both read as
    bound to a substring search, and neither scopes anything.
    """
    masked, literals = mask_literals(body)
    return any(
        literals[int(index)] == "inv.tenant_id"
        for index in _SETTING_CALL.findall(masked)
    )


def argument_names(args: str) -> list[str]:
    """Parameter names from ``pg_get_function_identity_arguments``."""
    names = []
    for part in args.split(","):
        tokens = part.strip().split()
        # "p_tenant uuid" has a name; a bare "uuid" does not.
        if len(tokens) > 1:
            names.append(tokens[0])
    return names


def filters_tenant_from_argument(body: str, args: str) -> bool:
    """Does the body filter ``tenant_id`` by a value the caller supplied?

    The first version asked whether an argument was *named* ``tenant``, which a
    rename defeats without changing one thing about the leak. What matters is
    the shape: a column called ``tenant_id`` compared against a parameter.
    """
    masked, _ = mask_literals(body)
    candidates = [re.escape(name) for name in argument_names(args)]
    candidates.append(r"\$\d+")
    pattern = re.compile(
        r"tenant_id\s*(?:::\w+)?\s*=\s*(?:" + "|".join(candidates) + r")\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(masked))


def search_path_of(config: list[str] | str | None) -> str | None:
    """The function's pinned ``search_path``, or ``None`` if it has none.

    ``proconfig`` is an array of ``name=value`` settings and a value may contain
    spaces — ``search_path=pg_temp, inv`` is one setting, not two. Joining the
    array and splitting on whitespace read that as ``pg_temp,`` and silently
    dropped the rest, which hid exactly the ordering this module checks.
    """
    if config is None:
        return None
    entries = [config] if isinstance(config, str) else list(config)
    for entry in entries:
        if entry.startswith("search_path="):
            return entry.split("=", 1)[1]
    return None


def temp_schema_misplaced(search_path: str | None) -> bool:
    """Is ``pg_temp`` resolved before the function's own schemas?

    ``pg_temp`` is where any caller can create objects. A definer function that
    resolves names through it first resolves them through something the caller
    controls, with the owner's rights — which is why PostgreSQL's own guidance
    is to put it last, and why a path that does not is a finding rather than a
    style note.
    """
    if not search_path:
        return False
    schemas = [part.strip() for part in search_path.split(",") if part.strip()]
    return "pg_temp" in schemas and schemas[-1] != "pg_temp"


def judge(body: str, args: str, config: list[str] | str | None) -> dict:
    """Everything the audit concludes from one function's source."""
    body = body or ""
    args = args or ""
    takes_tenant = "tenant" in args.lower() or filters_tenant_from_argument(body, args)
    search_path = search_path_of(config)
    return {
        "takesTenant": takes_tenant,
        "bindsTenant": binds_tenant_scope(body),
        "pinsSearchPath": search_path is not None,
        "searchPath": search_path,
        "tempSchemaMisplaced": temp_schema_misplaced(search_path),
    }
