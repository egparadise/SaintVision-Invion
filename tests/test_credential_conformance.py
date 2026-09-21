"""Test the test harness using a model and deliberate faults, not live secrets.

These results establish assertion coverage only. Filesystem actions here are
model states, not OS operations; a real backend must supply a separate harness.
"""

import pytest
from credential_conformance import CredentialConformance
from saintvision.credentials.contract import CredentialContext, CredentialDenied
from raises_no_skip import raises_without_skip

pytestmark = pytest.mark.credential_model


class ModelHarness:
    reference = "svcred:1:11111111-1111-4111-8111-111111111111:22222222-2222-4222-8222-222222222222"
    context = CredentialContext(
        "11111111-1111-4111-8111-111111111111",
        "prj_" + "0" * 26,
        "test-requester",
        "run_" + "0" * 26,
    )
    other_context_values = dict(
        tenant_id="33333333-3333-4333-8333-333333333333",
        project_id="prj_" + "1" * 26,
        subject_id="other-requester",
        run_id="run_" + "1" * 26,
    )
    purpose = "llm.invoke"
    destination = "provider-fixture"
    secret = b"synthetic-credential-never-a-real-token"

    def __init__(self, bug=None):
        self.bug, self.state, self.backend_reads = bug, None, 0
        self.resolver = self

    def mutate(self, action):
        self.state = action

    def resolve(self, reference, authenticated_context, purpose, destination_alias):
        if self.bug == "read_before_authorization":
            self.backend_reads += 1
        if reference != self.reference:
            raise CredentialDenied()
        if self.bug != "ignore_context" and authenticated_context != self.context:
            raise CredentialDenied()
        if purpose != self.purpose or destination_alias != self.destination:
            raise CredentialDenied()
        if self.state not in {None, "rotate_keep_old"}:
            raise CredentialDenied()
        return ModelHandle(self)


class ModelHandle:
    def __init__(self, harness):
        self.harness = harness

    def __repr__(self):
        return (
            self.harness.secret.decode()
            if self.harness.bug == "public_secret"
            else "<credential handle>"
        )

    def use(self, callback):
        h = self.harness
        if h.state == "backend_error_with_secret":
            try:
                raise OSError(h.secret.decode())
            except OSError as exc:
                if h.bug == "leak_exception":
                    raise CredentialDenied() from exc
                raise CredentialDenied() from None
        ignored = (h.bug == "ignore_revoke" and h.state == "revoke") or (
            h.bug == "ignore_file" and h.state == "file_symlink"
        )
        if h.state not in {None, "rotate_keep_old"} and not ignored:
            raise CredentialDenied()
        h.backend_reads += 1
        value = (
            b"synthetic-new-version"
            if h.bug == "retarget" and h.state == "rotate_keep_old"
            else h.secret
        )
        try:
            return callback(value)
        except TimeoutError:
            if h.bug == "retry_callback":
                return callback(value)
            raise


@pytest.fixture
def credential_harness():
    return ModelHarness()


class TestCredentialContractModel(CredentialConformance):
    """Reference model only; not backend acceptance."""


@pytest.mark.parametrize(
    "bug,method,args",
    [
        ("ignore_context", "test_wrong_context_denied_before_read", ("tenant_id",)),
        ("read_before_authorization", "test_invalid_reference_never_reads_backend", ("latest",)),
        ("ignore_revoke", "test_authority_rechecked_at_use", ("revoke",)),
        ("ignore_file", "test_filesystem_boundary_rechecked", ("file_symlink",)),
        ("retarget", "test_rotation_never_silently_retargets_old_reference", ()),
        ("public_secret", "test_handle_has_no_public_secret_representation", ()),
        ("retry_callback", "test_callback_failure_is_not_retried", ()),
    ],
)
def test_conformance_detects_deliberate_fault(bug, method, args):
    with raises_without_skip((AssertionError, pytest.fail.Exception)):
        getattr(CredentialConformance(), method)(ModelHarness(bug), *args)


def test_conformance_detects_secret_in_exception_chain(caplog, capsys):
    with raises_without_skip(AssertionError):
        CredentialConformance().test_backend_error_is_safe_in_trace_and_logs(
            ModelHarness("leak_exception"), caplog, capsys
        )
