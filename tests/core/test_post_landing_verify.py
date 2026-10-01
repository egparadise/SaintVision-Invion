"""`tools/post_landing_verify.py` against a fake `gh`, so nothing is ever dispatched.

The runner is the seam. `FakeRunner` answers `git` and `gh` from a scripted world and
**records every command**, which is what lets these cases assert the two things that matter
most and that no amount of output inspection would show:

* that `gh workflow run` was **not** called when a run already exists at the landed SHA, and
* that it was not called at all when the ref has moved.

A test that only checked the verdict would pass for a tool that dispatched six runners and
then reported correctly. The command log is the assertion.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.post_landing_verify import (  # noqa: E402
    LANES,
    PRE_FLIGHT,
    REQUIRED,
    VerifyRefused,
    build_evidence,
    commit_sha,
    judge_lane,
    main,
    matrix_matches,
    parser,
    remote_tip,
    render_markdown,
    run,
    validate_evidence,
)

LANDED = "6fc0428b" + "1" * 32
PREVIOUS = "d9c53e1a" + "2" * 32
OTHER = "486dab3e" + "3" * 32
REF = "integration/all-agents-unified"


def jobs_of(lane, conclusion="success"):
    """The job list GitHub would report for a lane, matrix legs included."""
    names = []
    for job_id, count in lane["jobs"].items():
        if count == 1:
            names.append(job_id)
        else:
            names.extend(f"{job_id} ({index})" for index in range(count))
    return [{"name": name, "conclusion": conclusion} for name in names]


class FakeRunner:
    """A scripted `git` and `gh`.

    `runs` maps a workflow file to the rows `gh run list` would print; `views` maps a run id
    to what `gh run view` would print. A dispatch appends a new row, so the "it appears
    after the dispatch" path is exercised rather than assumed.
    """

    def __init__(self, *, tip=LANDED, ancestor=True, known=(LANDED, PREVIOUS),
                 runs=None, views=None, dispatch_fails=(), ls_remote_fails=False,
                 dispatch_delay=0):
        self.tip = tip
        self.ancestor = ancestor
        self.known = set(known)
        self.runs = {workflow: list(rows) for workflow, rows in (runs or {}).items()}
        self.views = dict(views or {})
        self.dispatch_fails = set(dispatch_fails)
        self.ls_remote_fails = ls_remote_fails
        self.dispatch_delay = dispatch_delay
        self._pending: dict[str, list] = {}
        self.commands: list[list[str]] = []
        self._next_id = 9_000

    # -- helpers for the cases -----------------------------------------------------
    def dispatches(self):
        return [c[3] for c in self.commands if c[:3] == ["gh", "workflow", "run"]]

    def ran(self, *prefix):
        return [c for c in self.commands if c[: len(prefix)] == list(prefix)]

    # -- the runner ---------------------------------------------------------------
    def __call__(self, args, timeout=None):
        args = list(args)
        self.commands.append(args)
        if args[0] == "git":
            return self._git(args)
        if args[0] == "gh":
            return self._gh(args)
        raise AssertionError(f"unexpected command: {args}")

    def _git(self, args):
        if args[1] == "cat-file":
            return (0, "") if args[3].split("^")[0] in self.known else (1, "")
        if args[1] == "merge-base":
            return (0, "") if self.ancestor else (1, "")
        if args[1] == "ls-remote":
            if self.ls_remote_fails:
                return 1, ""
            return 0, f"{self.tip}\trefs/heads/{args[3].removeprefix('refs/heads/')}\n"
        raise AssertionError(f"unexpected git: {args}")

    def _gh(self, args):
        if args[1:3] == ["workflow", "run"]:
            workflow = args[3]
            if workflow in self.dispatch_fails:
                return 1, ""
            self._next_id += 1
            row = {
                "databaseId": self._next_id, "headSha": self.tip,
                "status": "completed", "conclusion": "success",
                "event": "workflow_dispatch", "createdAt": "2026-10-01T02:00:00Z",
            }
            if self.dispatch_delay:
                # GitHub creates the run a moment later, so the first listing does
                # not show it.
                self._pending[workflow] = [self.dispatch_delay, row]
            else:
                self.runs.setdefault(workflow, []).insert(0, row)
            lane = next(item for item in LANES if item["workflow"] == workflow)
            self.views[self._next_id] = {
                "status": "completed", "conclusion": "success", "headSha": self.tip,
                "event": "workflow_dispatch", "jobs": jobs_of(lane),
            }
            return 0, ""
        if args[1:3] == ["run", "list"]:
            workflow = args[args.index("--workflow") + 1]
            waiting = self._pending.get(workflow)
            if waiting:
                waiting[0] -= 1
                if waiting[0] <= 0:
                    self.runs.setdefault(workflow, []).insert(0, waiting[1])
                    self._pending.pop(workflow)
            return 0, json.dumps(self.runs.get(workflow, []))
        if args[1:3] == ["run", "view"]:
            return 0, json.dumps(self.views.get(int(args[3]), {}))
        raise AssertionError(f"unexpected gh: {args}")


def push_world(sha=LANDED, conclusion="success", *, skip=None, omit=None):
    """Every lane with a completed push run at `sha`, as a landing leaves things.

    `skip` names a lane whose jobs are reported `skipped`; `omit` names one whose required
    job is missing from the run altogether.
    """
    runs, views, identifier = {}, {}, 1_000
    for lane in LANES:
        identifier += 1
        runs[lane["workflow"]] = [{
            "databaseId": identifier, "headSha": sha, "status": "completed",
            "conclusion": "success", "event": "push",
            "createdAt": "2026-10-01T01:00:00Z",
        }]
        listed = jobs_of(lane, "skipped" if skip == lane["key"] else conclusion)
        if omit == lane["key"]:
            listed = listed[1:] or [{"name": "unrelated", "conclusion": "success"}]
        views[identifier] = {
            "status": "completed", "conclusion": "success", "headSha": sha,
            "event": "push", "jobs": listed,
        }
    return runs, views


def options(**overrides):
    values = {
        "landed": LANDED, "previous": PREVIOUS, "ref": REF,
        "poll_seconds": 0, "deadline_seconds": 10, "always_dispatch": False,
    }
    values.update(overrides)
    return type("Options", (), values)()


def go(runner, **overrides):
    return run(options(**overrides), runner, sleep=lambda _s: None, now=lambda: 0.0)


# --- the pass, and the dispatch that does not happen ------------------------------


def test_adopted_push_runs_pass_and_only_the_unpushed_lane_is_dispatched():
    """The landing's own runs are the evidence; only AC-11 needs starting.

    Five lanes trigger on push to integration, and those workflows set
    `cancel-in-progress: false` for that ref -- so dispatching them again would queue a
    second runner behind the first to learn the same thing.
    """
    runs, views = push_world()
    # AC-11 has no push trigger, so the landing left it with no run at this SHA.
    runs["ac11-security-scan.yml"] = []
    runner = FakeRunner(runs=runs, views=views)

    observations, facts = go(runner)

    assert {name: item["status"] for name, item in observations.items()} == {
        name: "MEASURED_PASS" for name in REQUIRED
    }
    assert runner.dispatches() == ["ac11-security-scan.yml"], (
        "a lane with a run at the landed SHA was dispatched again"
    )
    assert facts["adoptedWorkflows"] == sorted(
        lane["workflow"] for lane in LANES if lane["workflow"] != "ac11-security-scan.yml"
    )
    assert facts["dispatchedWorkflows"] == ["ac11-security-scan.yml"]


def test_always_dispatch_starts_every_lane():
    runs, views = push_world()
    runner = FakeRunner(runs=runs, views=views)
    observations, facts = go(runner, always_dispatch=True)
    assert sorted(runner.dispatches()) == sorted(lane["workflow"] for lane in LANES)
    assert facts["adoptedWorkflows"] == []
    assert all(observations[lane["key"]]["status"] == "MEASURED_PASS" for lane in LANES)


# --- a skipped job is not a pass --------------------------------------------------


def test_a_skipped_required_job_fails_the_lane_although_the_run_is_green():
    """The run concluded `success`. The axis was not observed.

    This is the shape that let a "rollback verified" step pass without a rollback, so it is
    judged at the job level, not the run level.
    """
    runs, views = push_world(skip="core")
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    core = observations["core"]
    assert core["status"] == "MEASURED_FAIL"
    assert core["skippedJobs"] == ["core", "s01-storage-roundtrip"], (
        "the skipped jobs were not named, so the record would not say what went unobserved"
    )
    assert core["runId"], "the run that failed to observe the axis is not named"
    assert observations["backend"]["status"] == "MEASURED_PASS", "one lane took down another"


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "None"])
def test_any_job_conclusion_other_than_success_fails_the_lane(conclusion):
    runs, views = push_world(conclusion=conclusion)
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    assert all(observations[lane["key"]]["status"] == "MEASURED_FAIL" for lane in LANES)


def test_a_missing_required_job_fails_the_lane():
    """A renamed or deleted job is not a green lane: the axis simply is not there."""
    runs, views = push_world(omit="securityCriticalHigh")
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    item = observations["securityCriticalHigh"]
    assert item["status"] == "MEASURED_FAIL"
    assert "security-critical-high" in item["missingJobs"]


def test_a_matrix_lane_needs_both_of_its_legs():
    """`backend` is two Python versions, and one of them passing is not the lane passing."""
    runs, views = push_world()
    identifier = next(iter(runs["backend.yml"]))["databaseId"]
    views[identifier]["jobs"] = [
        {"name": "backend (3.12)", "conclusion": "success"},
        {"name": "mlflow-live", "conclusion": "success"},
    ]
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    assert observations["backend"]["status"] == "MEASURED_FAIL"
    assert observations["backend"]["missingJobs"] == {
        "backend": {"expected": 2, "found": 1}
    }


# --- the pre-flight: nothing is dispatched when the question is wrong -------------


def test_a_moved_ref_dispatches_nothing():
    """The dispatch would describe another tree, so no CI time is spent at all."""
    runs, views = push_world(sha=LANDED)
    runner = FakeRunner(tip=OTHER, runs=runs, views=views)
    observations, facts = go(runner)
    assert observations["refIsAtLandedSha"]["status"] == "MEASURED_FAIL"
    assert observations["refIsAtLandedSha"]["refTipSha"] == OTHER
    assert runner.dispatches() == [], "a dispatch was sent for a ref that had moved"
    assert runner.ran("gh", "run", "list") == [], "runs were collected for the wrong tree"
    assert all(observations[lane["key"]]["status"] == "NOT_OBSERVED" for lane in LANES)
    assert facts["dispatchedWorkflows"] == []


def test_a_landing_that_is_not_a_fast_forward_dispatches_nothing():
    runner = FakeRunner(ancestor=False)
    observations, _ = go(runner)
    assert observations["landingWasFastForward"]["status"] == "MEASURED_FAIL"
    assert runner.dispatches() == []


def test_the_same_sha_twice_is_not_a_landing():
    runner = FakeRunner()
    observations, _ = go(runner, previous=LANDED)
    assert observations["landingWasFastForward"]["status"] == "MEASURED_FAIL"
    assert "nothing landed" in observations["landingWasFastForward"]["reason"]
    assert runner.dispatches() == []


def test_unjudgeable_ancestry_is_not_observed_rather_than_failed():
    """A shallow clone cannot answer, and "cannot tell" is not "no".

    The lanes are still observed: they are about the landed SHA either way. The verdict
    becomes NOT_OBSERVED, which is the honest outcome.
    """
    runs, views = push_world()
    runner = FakeRunner(known=(LANDED,), runs=runs, views=views)
    observations, _ = go(runner)
    first = observations["landingWasFastForward"]
    assert first["status"] == "NOT_OBSERVED"
    assert first["missingSha"] == PREVIOUS
    assert all(observations[lane["key"]]["status"] == "MEASURED_PASS" for lane in LANES)


def test_an_unreadable_ref_blocks_because_the_tree_cannot_be_confirmed():
    runner = FakeRunner(ls_remote_fails=True)
    observations, _ = go(runner)
    assert observations["refIsAtLandedSha"]["status"] == "NOT_OBSERVED"
    assert runner.dispatches() == []


def test_the_remote_tip_is_read_from_ls_remote_not_a_local_ref():
    """A local `origin/...` ref answers from the last fetch and can be hours stale."""
    runner = FakeRunner()
    assert remote_tip(runner, REF) == LANDED
    assert runner.commands[-1] == ["git", "ls-remote", "origin", f"refs/heads/{REF}"]
    assert not any("rev-parse" in " ".join(c) for c in runner.commands)


# --- a run at the wrong SHA is somebody else's evidence ---------------------------


def test_a_run_at_another_sha_is_not_adopted():
    """`gh run list` is not filtered by SHA, so the filter has to be ours."""
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    # Nothing at the landed SHA existed, so every lane was dispatched instead of adopting
    # the stale runs.
    assert sorted(runner.dispatches()) == sorted(lane["workflow"] for lane in LANES)
    assert all(observations[lane["key"]]["status"] == "MEASURED_PASS" for lane in LANES)


def test_a_dispatched_run_at_a_moved_sha_is_refused():
    """The ref can move between the dispatch and the run being created."""
    lane = LANES[0]
    item = judge_lane(
        lane, 123,
        {"status": "completed", "conclusion": "success", "headSha": OTHER,
         "jobs": jobs_of(lane)},
        LANDED, event="workflow_dispatch",
    )
    assert item["status"] == "MEASURED_FAIL"
    assert item["headSha"] == OTHER


def test_a_dispatched_run_must_have_an_id_above_the_ones_already_there():
    """Run ids increase, which identifies our run exactly without guessing at timestamps."""
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    for lane in LANES:
        chosen = observations[lane["key"]]["runId"]
        assert chosen > 9_000, "a pre-existing run was mistaken for the dispatched one"


def test_a_stale_completed_run_at_the_same_sha_is_not_the_dispatched_one():
    """The case the id floor exists for, and the only one that shows it.

    With `--always-dispatch` there is already a completed run at the landed SHA -- an
    earlier attempt, say, whose jobs failed. GitHub creates the new run a moment
    after the dispatch returns, so the first listing still shows only the old one. A
    tool that took "the newest run at this SHA" would report the old failure as the
    result of the run it just started.
    """
    runs, views = push_world(conclusion="failure")
    runner = FakeRunner(runs=runs, views=views, dispatch_delay=2)
    observations, facts = go(runner, always_dispatch=True)
    for lane in LANES:
        item = observations[lane["key"]]
        assert item["status"] == "MEASURED_PASS", (
            f"{lane['key']} reported the stale run: {item.get('reason')}"
        )
        assert item["runId"] > 9_000, "the stale run was adopted as ours"
    assert facts["adoptedWorkflows"] == []


def test_a_dispatch_that_fails_is_a_failed_lane_not_a_silent_pass():
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views, dispatch_fails={"docs.yml"})
    observations, _ = go(runner)
    assert observations["docs"]["status"] == "MEASURED_FAIL"
    assert observations["docs"]["reason"].startswith("the workflow could not be dispatched")


def test_a_run_that_never_completes_is_not_observed():
    runs, views = push_world()
    for view in views.values():
        view["status"] = "in_progress"
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner, deadline_seconds=-1)
    assert all(observations[lane["key"]]["status"] == "NOT_OBSERVED" for lane in LANES)
    assert all(
        "deadline" in observations[lane["key"]]["reason"] for lane in LANES
    )


def test_a_run_reporting_no_jobs_is_not_observed():
    lane = LANES[0]
    item = judge_lane(
        lane, 7, {"status": "completed", "headSha": LANDED, "jobs": []},
        LANDED, event="push",
    )
    assert item["status"] == "NOT_OBSERVED"


# --- the record -------------------------------------------------------------------


def provenance(**overrides):
    values = {
        "commit_sha": "a" * 40, "branch": "agent/claude/c164",
        "working_tree_clean_status": False, "content_clean_diff": True,
        "executor": "claude",
    }
    values.update(overrides)
    return values


def evidence_for(runner=None, **overrides):
    import datetime as dt

    runs, views = push_world()
    runner = runner or FakeRunner(runs=runs, views=views)
    observations, facts = go(runner)
    moment = dt.datetime(2026, 10, 1, 2, 0, tzinfo=dt.timezone.utc)
    document = build_evidence(observations, facts, provenance(**overrides), moment, moment)
    return document


def test_the_evidence_validates_and_promotes_nothing():
    document = evidence_for()
    validate_evidence(document)
    assert document["verdict"] == "PASS"
    assert document["promotesScore"] is False
    assert set(document["observations"]) == set(REQUIRED)
    assert set(document["criteria"]) == set(REQUIRED)


def test_untracked_output_does_not_block_the_next_run():
    """This tool writes evidence into the repo, so its own output must not be a blocker.

    A *tracked* modification still is: that would mean the collector's own source differs
    from the commit the record names.
    """
    validate_evidence(evidence_for(working_tree_clean_status=False, content_clean_diff=True))
    with pytest.raises(ValueError, match="uncommitted tracked changes"):
        validate_evidence(evidence_for(content_clean_diff=False))


def test_a_verdict_that_was_not_recomputed_is_refused():
    document = evidence_for()
    document["verdict"] = "PASS"
    document["observations"]["docs"] = {"status": "MEASURED_FAIL", "reason": "x"}
    with pytest.raises(ValueError, match="verdict was not recomputed"):
        validate_evidence(document)


def test_a_lane_cannot_pass_without_naming_its_run():
    document = evidence_for()
    document["observations"]["docs"].pop("runId")
    with pytest.raises(ValueError, match="passed without naming a run"):
        validate_evidence(document)


def test_a_record_that_claims_to_promote_a_score_is_refused():
    document = evidence_for()
    document["promotesScore"] = True
    with pytest.raises(ValueError, match="never promotes a score"):
        validate_evidence(document)


def test_the_criteria_are_bound_to_the_lanes_as_configured():
    document = evidence_for()
    document["criteria"] = dict(document["criteria"], docs="something else")
    with pytest.raises(ValueError, match="criteria binding mismatch"):
        validate_evidence(document)


def test_the_markdown_names_the_runs_and_says_it_promotes_nothing():
    document = evidence_for()
    text = render_markdown(document)
    assert "promotes no score" in text
    for lane in LANES:
        assert str(document["observations"][lane["key"]]["runId"]) in text
    assert document["source"]["landedSha"] in text
    for name in PRE_FLIGHT:
        assert name in text


# --- the lane table itself --------------------------------------------------------


def test_the_ac11_lane_is_named_by_its_file_not_its_check():
    """The check is `security-critical-high`; the file is `ac11-security-scan.yml`.

    Guessing the file from the check name would silently fail to dispatch the one lane this
    tool exists for, and the failure would look like "no run appeared".
    """
    lane = next(item for item in LANES if item["key"] == "securityCriticalHigh")
    assert lane["workflow"] == "ac11-security-scan.yml"
    assert lane["jobs"] == {"security-critical-high": 1}


def test_every_configured_workflow_file_exists():
    """A renamed workflow must break here, not three hours into a landing."""
    for lane in LANES:
        assert (ROOT / ".github/workflows" / lane["workflow"]).is_file(), lane["workflow"]


def test_every_configured_job_id_exists_in_its_workflow():
    for lane in LANES:
        text = (ROOT / ".github/workflows" / lane["workflow"]).read_text(encoding="utf-8")
        for job_id in lane["jobs"]:
            assert f"\n  {job_id}:" in text, f"{job_id} is not a job of {lane['workflow']}"


def test_every_lane_is_dispatchable():
    """`gh workflow run` needs the trigger to be declared in the file."""
    for lane in LANES:
        text = (ROOT / ".github/workflows" / lane["workflow"]).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text, lane["workflow"]


@pytest.mark.parametrize("names,job_id,expected", [
    (["backend (3.12)", "backend (3.14)"], "backend", 2),
    (["backend"], "backend", 1),
    (["backend-extra"], "backend", 0),
    (["core", "s01-storage-roundtrip"], "core", 1),
])
def test_a_job_id_matches_itself_and_its_matrix_legs_only(names, job_id, expected):
    assert len(matrix_matches(names, job_id)) == expected


# --- the command line -------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "6fc0428b", "z" * 40, LANDED + "0", " "])
def test_a_short_or_non_hex_sha_is_refused(bad):
    with pytest.raises(VerifyRefused):
        commit_sha(bad, "landed")


def test_a_sha_is_accepted_case_insensitively_and_normalised():
    assert commit_sha("  " + LANDED.upper() + "  ", "landed") == LANDED


def test_dry_run_dispatches_nothing_and_prints_the_plan(capsys):
    runner = FakeRunner()
    code = main(["--landed", LANDED, "--previous", PREVIOUS, "--dry-run"], runner=runner)
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["dispatched"] is False
    assert set(printed["lanes"].values()) == {lane["workflow"] for lane in LANES}
    assert runner.commands == [], "--dry-run ran a command"


def test_the_defaults_are_the_integration_ref_and_a_long_interval():
    args = parser().parse_args(["--landed", LANDED, "--previous", PREVIOUS])
    assert args.ref == REF
    assert args.poll_seconds >= 60, "a short interval spends API quota for nothing"
    assert args.always_dispatch is False
