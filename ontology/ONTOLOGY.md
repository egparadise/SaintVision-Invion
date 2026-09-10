# Ontology 0.2.0

schema.ttl = TBox; example.ttl/example.jsonld = the same ABox; shapes.ttl = constraints. The ABox contains 48 development tasks with registry status and a synthetic runtime example. Synthetic IDs, checksums, resource values and times are fixtures, not observations.

Run `python tools/check_ontology.py` to check parsing, defined terms, graph equivalence, task registry alignment, SHACL valid/invalid examples and four competency queries. Product runtime invariants still require SQL, policy and integration tests.
