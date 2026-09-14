# INV contracts v1alpha1

`v1alpha1/core.schema.json` is the authoritative JSON Schema 2020-12 bundle. Every object has closed fields; boundary validators enforce formats, constraints and unknown-field rejection. Generated Pydantic/TypeScript/Go declarations provide developer types; they are not authorization or a replacement for JSON Schema validation.

Use `python tools/generate_contracts.py` then commit all generated outputs. CI regenerates and compares. Fencing tokens are `recovery-epoch-UUID:decimal-sequence` strings on the wire to avoid JavaScript integer truncation. Sizes use bytes, CPU uses millicores, times are RFC3339 with a timezone, trace IDs are W3C 32-hex strings.

The initial bundle establishes contracts for Claude service implementation and Gemini API integration. It does not imply that mutation endpoints, OIDC, Node execution or the full UI exist.

`credential-reference.schema.json` defines the version-pinned internal credential reference (ADR-075). It adds no public API authority and does not implement a secret resolver. Authorization and resolution are server-side obligations in the operating credential contract.
