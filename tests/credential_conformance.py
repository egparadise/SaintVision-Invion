"""Reusable ADR-075 security assertions for an implementation-owned harness.

Subclass CredentialConformance and supply credential_harness. The harness must
provide a real resolver, reference/context/purpose/destination, synthetic secret,
backend_reads counter, and mutate(action). See the contract document for action
semantics. No default fixture, live secret lookup, dynamic plugin import or
production acceptance is provided here.
"""

from dataclasses import replace
import json
import traceback
import pytest
from saintvision.credentials.contract import CredentialDenied


class CredentialConformance:
    def resolve(self, h, **changes):
        args = dict(
            reference=h.reference,
            authenticated_context=h.context,
            purpose=h.purpose,
            destination_alias=h.destination,
        )
        args.update(changes)
        return h.resolver.resolve(**args)

    def test_authorized_callback_once(self, credential_harness):
        h = credential_harness
        handle = self.resolve(h)
        calls = []

        def consume(secret):
            assert secret == h.secret
            calls.append(True)
            return "adapter-result"

        assert handle.use(consume) == "adapter-result"
        assert calls == [True]

    @pytest.mark.parametrize("field", ["tenant_id", "project_id", "subject_id", "run_id"])
    def test_wrong_context_denied_before_read(self, credential_harness, field):
        h = credential_harness
        altered = replace(h.context, **{field: h.other_context_values[field]})
        before = h.backend_reads
        with pytest.raises(CredentialDenied):
            self.resolve(h, authenticated_context=altered)
        assert h.backend_reads == before

    @pytest.mark.parametrize(
        "field,value", [("purpose", "git.publish"), ("destination_alias", "other-provider")]
    )
    def test_wrong_target_denied_before_read(self, credential_harness, field, value):
        h = credential_harness
        before = h.backend_reads
        with pytest.raises(CredentialDenied):
            self.resolve(h, **{field: value})
        assert h.backend_reads == before

    @pytest.mark.parametrize(
        "reference",
        ["latest", "C:/secret.pem", "/etc/secret", "https://example.invalid/key", "raw-token", ""],
    )
    def test_invalid_reference_never_reads_backend(self, credential_harness, reference):
        h = credential_harness
        before = h.backend_reads
        with pytest.raises(CredentialDenied):
            self.resolve(h, reference=reference)
        assert h.backend_reads == before

    @pytest.mark.parametrize(
        "action",
        ["revoke", "disable", "expire", "revoke_grant", "remove_version", "rebind_destination"],
    )
    def test_authority_rechecked_at_use(self, credential_harness, action):
        h = credential_harness
        handle = self.resolve(h)
        h.mutate(action)
        calls = []
        with pytest.raises(CredentialDenied):
            handle.use(lambda secret: calls.append(True))
        assert calls == []

    @pytest.mark.parametrize(
        "action",
        ["revoke", "disable", "expire", "revoke_grant", "remove_version", "rebind_destination"],
    )
    def test_unavailable_reference_cannot_resolve(self, credential_harness, action):
        h = credential_harness
        h.mutate(action)
        before = h.backend_reads
        with pytest.raises(CredentialDenied):
            self.resolve(h)
        assert h.backend_reads == before

    def test_each_use_rechecks_revocation(self, credential_harness):
        h = credential_harness
        handle = self.resolve(h)
        assert handle.use(lambda secret: "first") == "first"
        h.mutate("revoke")
        calls = []
        with pytest.raises(CredentialDenied):
            handle.use(lambda secret: calls.append(True))
        assert calls == []

    def test_rotation_never_silently_retargets_old_reference(self, credential_harness):
        h = credential_harness
        old = self.resolve(h)
        h.mutate("rotate_keep_old")
        seen = []
        old.use(lambda secret: seen.append(secret))
        assert seen == [h.secret]

    @pytest.mark.parametrize(
        "action",
        [
            "root_symlink",
            "root_replaced",
            "file_symlink",
            "file_replaced",
            "wrong_owner",
            "public_mode",
            "non_regular",
            "oversize",
            "outside_root",
        ],
    )
    def test_filesystem_boundary_rechecked(self, credential_harness, action):
        h = credential_harness
        handle = self.resolve(h)
        h.mutate(action)
        calls = []
        with pytest.raises(CredentialDenied):
            handle.use(lambda secret: calls.append(True))
        assert calls == []

    def test_handle_has_no_public_secret_representation(self, credential_harness):
        h = credential_harness
        handle = self.resolve(h)
        assert h.secret.decode() not in str(handle) + repr(handle)
        with pytest.raises(TypeError):
            json.dumps(handle)

    def test_backend_error_is_safe_in_trace_and_logs(self, credential_harness, caplog, capsys):
        h = credential_harness
        handle = self.resolve(h)
        h.mutate("backend_error_with_secret")
        calls = []
        with pytest.raises(CredentialDenied) as caught:
            handle.use(lambda secret: calls.append(True))
        rendered = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
        output = capsys.readouterr()
        assert h.secret.decode() not in rendered + caplog.text + output.out + output.err
        assert calls == []

    def test_callback_failure_is_not_retried(self, credential_harness):
        handle = self.resolve(credential_harness)
        calls = []

        def fail(secret):
            calls.append(True)
            raise TimeoutError("synthetic ambiguous external effect")

        # Implementations may map the error, but must not retry or report success.
        with pytest.raises((CredentialDenied, TimeoutError)):
            handle.use(fail)
        assert calls == [True]
