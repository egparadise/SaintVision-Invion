"""MLflow mirror (S10-BE, design PR #168 v1.3, decision B).

The lineage database is the source of truth for experiments, runs, model
versions and deployments. MLflow, when configured, receives a *mirror* of that
truth and never feeds anything back into a decision. This package holds the
parts of the mirror that do not talk to a tracking server:

* :mod:`.canonical` -- the canonical payload bytes and ``payload_sha256``, and
  the tracking URI normalisation behind ``tracking_uri_sha256``;
* :mod:`.codes` -- the ``TRACK-0001``..``TRACK-0005`` family with its status,
  retryability, mirror status and evidence verdict, stated per code;
* :mod:`.config` -- the strict ``INV_MLFLOW_*`` settings and their readiness.

The sink contract and its conformance suite live in
:mod:`saintvision.adapters.tracking`; the tables and the enqueue/deliver
services in :mod:`saintvision.db.models.tracking` and
:mod:`saintvision.services.tracking`. A real MLflow HTTP client and the
operator service credential are stage 2 and are deliberately absent here.
"""
