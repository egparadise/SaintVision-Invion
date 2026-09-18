"""Option-A license read-through (VF-CL-03/CL-05): license lives in the kernel
manifest and is served by (modelId, version) -- the key a public model_version
carries.

finding #2 was resolved on the Claude side as option A: no license column is added
to public.model_versions; license and classification stay owned by the kernel
manifest that deployment admission enforces, and the registry relates to it by
(model_id, version). This exercises the kernel end of that read-through -- a
committed manifest serves licensePolicy and classification, retrieved by that key
-- reusing the kernel commit fixture. The app end (a model_version carrying the
same key) is pinned in tests/test_model_registry.py.
"""

import pytest

from test_model_commit import commit, model  # noqa: F401
from test_storage_commit import sample, storage_subject  # noqa: F401  (fixture chain for model)

pytestmark = pytest.mark.postgres


def test_committed_manifest_serves_license_and_classification_by_model_key(model):
    a = model
    commit(a)
    got = a.store.get(a.principal, a.e.project, a.body["modelId"], a.body["version"])
    manifest = got["manifest"]
    # Retrieved by (modelId, version); the license and classification the manifest
    # carries are what a model_version reads through rather than storing itself.
    assert (manifest["modelId"], manifest["version"]) == (
        a.body["modelId"], a.body["version"],
    )
    assert manifest["licensePolicy"]
    assert manifest["classification"]
    assert got["committed"] and got["requiresExecutionRevalidation"]
