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
    DEFAULT_REF,
    DISPATCH_EVENT,
    LANES,
    PRE_FLIGHT,
    REQUIRED,
    VerifyRefused,
    REF_EVENTS,
    build_evidence,
    dispatch_named,
    candidates_at_sha,
    commit_sha,
    judge_lane,
    main,
    matrix_matches,
    new_correlation_id,
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
                 dispatch_delay=0, rival_dispatch=(), rival_first=()):
        self.tip = tip
        self.ancestor = ancestor
        self.known = set(known)
        self.runs = {workflow: list(rows) for workflow, rows in (runs or {}).items()}
        self.views = dict(views or {})
        self.dispatch_fails = set(dispatch_fails)
        self.ls_remote_fails = ls_remote_fails
        #: When true the fake ignores `--branch`, so the tool's own check filters.
        self.unfiltered = False
        self.dispatch_delay = dispatch_delay
        #: Workflows where somebody else's dispatch lands at the same SHA alongside ours.
        self.rival_dispatch = set(rival_dispatch)
        #: Workflows where somebody else's dispatch run becomes visible *before* ours. This
        #: is the shape that defeats any rule based on watching the list.
        self.rival_first = set(rival_first)
        #: correlation ids this fake was dispatched with, per workflow.
        self.correlation_ids: dict[str, list[str]] = {}
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
            given = [a for a in args if a.startswith("correlation_id=")]
            assert len(given) == 1, f"no correlation id was passed: {args}"
            correlation_id = given[0].split("=", 1)[1]
            assert correlation_id, "the correlation id was empty"
            self.correlation_ids.setdefault(workflow, []).append(correlation_id)
            if workflow in self.rival_first:
                # Somebody else's dispatch is registered first and is visible immediately;
                # ours follows a poll later. Any rule that binds "the candidate in this
                # poll" takes theirs.
                self._next_id += 1
                theirs = {
                    "databaseId": self._next_id, "headSha": self.tip, "headBranch": REF,
                    "displayTitle": "someone-elses-dispatch", "status": "completed",
                    "conclusion": "failure", "event": "workflow_dispatch",
                    "createdAt": "2026-10-01T01:59:00Z",
                }
                self.runs.setdefault(workflow, []).insert(0, theirs)
                self.views[theirs["databaseId"]] = {
                    "status": "completed", "conclusion": "failure", "headSha": self.tip,
                    "headBranch": REF, "event": "workflow_dispatch",
                    "displayTitle": "someone-elses-dispatch",
                    "jobs": jobs_of(next(i for i in LANES if i["workflow"] == workflow),
                                    "failure"),
                }
            self._next_id += 1
            row = {
                "databaseId": self._next_id, "headSha": self.tip,
                "headBranch": REF, "displayTitle": correlation_id,
                "status": "completed", "conclusion": "success",
                "event": "workflow_dispatch", "createdAt": "2026-10-01T02:00:00Z",
            }
            if workflow in self.rival_dispatch:
                # A second run carrying *our own* id -- only possible if an id were reused.
                self._next_id += 1
                rival = dict(row, databaseId=self._next_id)
                self.runs.setdefault(workflow, []).insert(0, rival)
                self.views[rival["databaseId"]] = {
                    "status": "completed", "conclusion": "failure", "headSha": self.tip,
                    "headBranch": REF, "event": "workflow_dispatch",
                    "jobs": jobs_of(next(i for i in LANES if i["workflow"] == workflow),
                                    "failure"),
                }
            if self.dispatch_delay:
                # GitHub creates the run a moment later, so the first listing does
                # not show it.
                self._pending[workflow] = [self.dispatch_delay, row]
            else:
                self.runs.setdefault(workflow, []).insert(0, row)
            lane = next(item for item in LANES if item["workflow"] == workflow)
            self.views[row["databaseId"]] = {
                "status": "completed", "conclusion": "success", "headSha": self.tip,
                "headBranch": REF, "event": "workflow_dispatch",
                "displayTitle": correlation_id, "jobs": jobs_of(lane),
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
            # `gh run list --branch` filters server side. The tool checks `headBranch`
            # again anyway, and `test_the_branch_is_checked_in_code_too` relies on this
            # fake NOT filtering when asked for one branch while rows name another.
            branch = args[args.index("--branch") + 1] if "--branch" in args else None
            rows = self.runs.get(workflow, [])
            if branch is not None and not self.unfiltered:
                rows = [r for r in rows if r.get("headBranch") == branch]
            return 0, json.dumps(rows)
        if args[1:3] == ["run", "view"]:
            return 0, json.dumps(self.views.get(int(args[3]), {}))
        raise AssertionError(f"unexpected gh: {args}")


def push_world(sha=LANDED, conclusion="success", *, skip=None, omit=None,
               branch=REF, event="push"):
    """Every lane with a completed run at `sha`, as a landing leaves things.

    `skip` names a lane whose jobs are reported `skipped`; `omit` names one whose required
    job is missing from the run altogether. `branch` and `event` are what make a run a run
    *of the ref*, so the cases below vary them.
    """
    runs, views, identifier = {}, {}, 1_000
    for lane in LANES:
        identifier += 1
        runs[lane["workflow"]] = [{
            "databaseId": identifier, "headSha": sha, "headBranch": branch,
            "displayTitle": "Merge PR into merge train",
            "status": "completed", "conclusion": "success", "event": event,
            "createdAt": "2026-10-01T01:00:00Z",
        }]
        listed = jobs_of(lane, "skipped" if skip == lane["key"] else conclusion)
        if omit == lane["key"]:
            listed = listed[1:] or [{"name": "unrelated", "conclusion": "success"}]
        views[identifier] = {
            "status": "completed", "conclusion": "success", "headSha": sha,
            "headBranch": branch, "event": event, "jobs": listed,
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
    """A clock that advances one second per read.

    A frozen clock cannot reach a deadline, so `wait_for` would spin forever on a lane whose
    run never appears -- which is how this harness first hung.
    """
    ticks = iter(range(10_000))

    return run(
        options(**overrides), runner,
        sleep=lambda _s: None, now=lambda: float(next(ticks)),
    )


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
        LANDED, REF, event="workflow_dispatch",
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
        lane,
        7,
        {"status": "completed", "headSha": LANDED, "headBranch": REF,
         "event": "push", "jobs": []},
        LANDED,
        REF,
        event="push",
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


# --- a run has to be a run *of the ref* -------------------------------------------


def test_a_pull_request_run_at_the_landed_sha_is_not_adopted():
    """A fast-forward landing leaves pull-request runs carrying the landed SHA.

    For a pull request GitHub reports the PR head as `headSha`. When the branch that landed
    was the PR's own branch, its PR runs name this very commit while describing a merge of
    somebody's branch -- not the integration ref. Adopting one would report a different
    question's answer.
    """
    runs, views = push_world(branch="agent/someone/feature", event="pull_request")
    runner = FakeRunner(runs=runs, views=views)
    observations, facts = go(runner)
    assert sorted(runner.dispatches()) == sorted(lane["workflow"] for lane in LANES), (
        "a pull-request run was adopted instead of dispatching"
    )
    assert facts["adoptedWorkflows"] == []
    for lane in LANES:
        assert observations[lane["key"]]["runId"] > 9_000


def test_a_push_run_of_another_branch_at_the_same_sha_is_not_adopted():
    """Two branches can point at one commit; only one of them is the ref we mean."""
    runs, views = push_world(branch="main", event="push")
    runner = FakeRunner(runs=runs, views=views)
    observations, facts = go(runner)
    assert facts["adoptedWorkflows"] == []
    assert sorted(runner.dispatches()) == sorted(lane["workflow"] for lane in LANES)


def test_the_listing_is_narrowed_by_branch():
    runs, views = push_world()
    runner = FakeRunner(runs=runs, views=views)
    go(runner)
    listings = runner.ran("gh", "run", "list")
    assert listings, "no run listing was made"
    for command in listings:
        assert "--branch" in command and command[command.index("--branch") + 1] == REF


def test_the_branch_is_checked_in_code_too():
    """A filter we asked a tool for is not a fact we observed.

    With the fake ignoring `--branch`, the only thing standing between a foreign run and
    adoption is the tool's own `headBranch` comparison.
    """
    runs, views = push_world(branch="main", event="push")
    runner = FakeRunner(runs=runs, views=views)
    runner.unfiltered = True
    _, facts = go(runner)
    assert facts["adoptedWorkflows"] == [], "the server-side filter was the only check"


@pytest.mark.parametrize("branch,event,expected", [
    (REF, "push", True),
    (REF, "workflow_dispatch", True),
    (REF, "pull_request", False),
    ("main", "push", False),
    ("agent/x/y", "workflow_dispatch", False),
])
def test_candidates_require_the_sha_the_branch_and_the_event(branch, event, expected):
    rows = [{
        "databaseId": 5, "headSha": LANDED, "headBranch": branch, "event": event,
        "status": "completed", "conclusion": "success",
    }]
    found = candidates_at_sha(rows, LANDED, REF, events=REF_EVENTS)
    assert bool(found) is expected


def test_candidates_come_back_newest_first():
    rows = [
        {"databaseId": n, "headSha": LANDED, "headBranch": REF, "event": "push"}
        for n in (3, 11, 7)
    ]
    assert [row["databaseId"] for row in candidates_at_sha(rows, LANDED, REF,
                                                           events=REF_EVENTS)] == [11, 7, 3]


# --- two rival dispatches: say so rather than choose -------------------------------


def test_a_rival_dispatch_before_the_baseline_does_not_make_it_ambiguous():
    """The id floor still does its work: an earlier dispatch is not a candidate."""
    runs, views = push_world()
    # An older dispatch of every lane, at the landed SHA, that is not ours.
    for lane in LANES:
        runs[lane["workflow"]].append({
            "databaseId": 900, "headSha": LANDED, "headBranch": REF,
            "displayTitle": "an-earlier-dispatch",
            "event": "workflow_dispatch", "status": "completed", "conclusion": "failure",
            "createdAt": "2026-09-30T23:00:00Z",
        })
    views[900] = {
        "status": "completed", "conclusion": "failure", "headSha": LANDED,
        "headBranch": REF, "event": "workflow_dispatch",
        "jobs": [{"name": "x", "conclusion": "failure"}],
    }
    runner = FakeRunner(runs=runs, views=views, dispatch_delay=2)
    observations, _ = go(runner, always_dispatch=True)
    for lane in LANES:
        item = observations[lane["key"]]
        assert item["status"] == "MEASURED_PASS", item.get("reason")
        assert item["runId"] > 9_000


# --- judge_lane re-reads what the run says about itself ----------------------------


@pytest.mark.parametrize("field,value,fragment", [
    ("headSha", OTHER, "headSha is not the landed SHA"),
    ("headBranch", "main", "not a run of the integration ref"),
    ("event", "pull_request", "event that does not describe the ref"),
])
def test_a_run_that_describes_something_else_is_refused(field, value, fragment):
    lane = LANES[0]
    view = {
        "status": "completed", "conclusion": "success", "headSha": LANDED,
        "headBranch": REF, "event": "push", "jobs": jobs_of(lane),
    }
    view[field] = value
    item = judge_lane(lane, 123, view, LANDED, REF, event="push")
    assert item["status"] == "MEASURED_FAIL"
    assert fragment in item["reason"]


def test_the_run_view_asks_for_the_branch_and_the_event():
    runs, views = push_world()
    runner = FakeRunner(runs=runs, views=views)
    go(runner)
    for command in runner.ran("gh", "run", "view"):
        fields = command[command.index("--json") + 1]
        assert "headBranch" in fields and "event" in fields


def test_a_passing_lane_records_the_branch_and_the_event():
    runs, views = push_world()
    runner = FakeRunner(runs=runs, views=views)
    observations, _ = go(runner)
    for lane in LANES:
        item = observations[lane["key"]]
        assert item["headBranch"] == REF
        assert item["event"] in REF_EVENTS


def test_the_dispatch_event_name_is_the_one_github_uses():
    assert DISPATCH_EVENT == "workflow_dispatch"
    assert DISPATCH_EVENT in REF_EVENTS and "push" in REF_EVENTS
    assert "pull_request" not in REF_EVENTS


# --- the correlation id: the probe that defeated watching the list -----------------


def test_a_rival_dispatch_visible_first_is_not_bound():
    """The regression probe for the finding this mechanism exists for.

    Another operator dispatches the same workflow on the same ref at the same commit a
    moment before us, and *their* run is the only candidate in the first poll; ours appears
    in the next. Every rule built on watching the list binds theirs -- "newest at this SHA"
    does, and so does "exactly one candidate in this poll", because in that poll there is
    exactly one and it is not ours. Only the name decides.
    """
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(
        runs=runs, views=views,
        rival_first={"docs.yml", "ac11-security-scan.yml"},
        dispatch_delay=2,
    )
    observations, _ = go(runner)
    for key, workflow in (("docs", "docs.yml"), ("securityCriticalHigh", "ac11-security-scan.yml")):
        item = observations[key]
        assert item["status"] == "MEASURED_PASS", (
            f"{key} bound somebody else's run: {item.get('reason')}"
        )
        ours = runner.correlation_ids[workflow][0]
        assert item["correlationId"] == ours
        bound = item["runId"]
        theirs = [
            row["databaseId"] for row in runner.runs[workflow]
            if row.get("displayTitle") == "someone-elses-dispatch"
        ]
        assert theirs, "the probe did not create a rival run"
        assert bound not in theirs, "the rival run was bound"


def test_the_correlation_id_is_passed_on_every_dispatch():
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views)
    go(runner)
    sent = [c for c in runner.commands if c[:3] == ["gh", "workflow", "run"]]
    assert len(sent) == len(LANES)
    seen = set()
    for command in sent:
        assert "-f" in command
        value = command[command.index("-f") + 1]
        assert value.startswith("correlation_id=post-landing-verify/")
        seen.add(value)
    assert len(seen) == len(LANES), "two lanes shared one correlation id"


def test_a_correlation_id_is_opaque_and_fresh():
    first, second = new_correlation_id(), new_correlation_id()
    assert first != second
    assert first.startswith("post-landing-verify/") and len(first) > 30
    # Nothing about the host, the user or the repository goes into it.
    assert first.split("/", 1)[1].isalnum()


def test_the_list_is_re_read_until_our_run_appears():
    """Binding happens on a later poll, so the listing cannot be a one-shot read."""
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views, dispatch_delay=3)
    observations, _ = go(runner)
    assert all(observations[lane["key"]]["status"] == "MEASURED_PASS" for lane in LANES)
    for lane in LANES:
        listings = [
            c for c in runner.ran("gh", "run", "list")
            if lane["workflow"] in c
        ]
        assert len(listings) > 1, f"{lane['key']} was listed once and never again"


@pytest.mark.parametrize("field,value", [
    ("displayTitle", "someone-elses-dispatch"),
    ("headSha", OTHER),
    ("headBranch", "main"),
    ("event", "push"),
])
def test_a_named_dispatch_still_has_to_agree_on_everything_else(field, value):
    """A name is a claim; the SHA, branch and event are what make the run ours."""
    row = {
        "databaseId": 10, "headSha": LANDED, "headBranch": REF,
        "displayTitle": "post-landing-verify/abc", "event": "workflow_dispatch",
    }
    assert dispatch_named([row], LANDED, REF, "post-landing-verify/abc")
    assert not dispatch_named([dict(row, **{field: value})], LANDED, REF,
                              "post-landing-verify/abc")


def test_a_run_never_carrying_our_id_is_not_observed():
    """The deadline, and a reason that says what was looked for."""
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views, dispatch_delay=10_000)
    observations, _ = go(runner, deadline_seconds=3)
    for lane in LANES:
        item = observations[lane["key"]]
        assert item["status"] == "NOT_OBSERVED"
        assert "correlation id" in item["reason"]
        assert item["correlationId"]


def test_two_runs_carrying_one_id_are_not_observed():
    """One id cannot name two runs unless something re-used it; say so rather than pick."""
    runs, views = push_world(sha=OTHER)
    runner = FakeRunner(runs=runs, views=views, rival_dispatch={"docs.yml"})
    observations, _ = go(runner)
    item = observations["docs"]
    assert item["status"] == "NOT_OBSERVED"
    assert len(item["candidateRunIds"]) == 2
    assert "correlation id" in item["reason"]


def test_the_run_listing_asks_for_the_display_title():
    runs, views = push_world()
    runner = FakeRunner(runs=runs, views=views)
    go(runner)
    for command in runner.ran("gh", "run", "list"):
        assert "displayTitle" in command[command.index("--json") + 1]


# --- the workflow change touches only the run name ---------------------------------


WORKFLOW_DIR = ROOT / ".github/workflows"
NL = chr(10)
RUN_NAME = "run-name: ${{ inputs.correlation_id || github.workflow }}"


def workflow_text(lane):
    return (WORKFLOW_DIR / lane["workflow"]).read_text(encoding="utf-8")


def test_every_lane_accepts_the_correlation_id_input():
    """`gh workflow run -f correlation_id=...` fails outright if the input is undeclared."""
    for lane in LANES:
        text = workflow_text(lane)
        assert "      correlation_id:" in text, lane["workflow"]
        assert RUN_NAME in text, lane["workflow"]


def test_the_input_is_read_nowhere_but_the_run_name():
    """This is what "no behaviour change outside the dispatch path" means, mechanically.

    A value that appears only in `run-name` cannot reach a job, a step, an `if:` or an env
    var, so no workflow can behave differently because of it. Checking that is stronger than
    asserting the diff was small.
    """
    for lane in LANES:
        lines = [
            line for line in workflow_text(lane).splitlines()
            if "correlation_id" in line and not line.lstrip().startswith("#")
        ]
        assert lines, lane["workflow"]
        for line in lines:
            assert (
                line == RUN_NAME
                or line.strip() == "correlation_id:"
            ), f"{lane['workflow']} reads correlation_id outside run-name: {line!r}"


def test_the_input_is_optional_so_a_manual_run_needs_nothing():
    for lane in LANES:
        text = workflow_text(lane)
        after = text.split("      correlation_id:", 1)[1].splitlines()
        block = NL.join(
            line for line in after
            if line.startswith("        ") or not line.strip()
        )
        assert "required: false" in block, lane["workflow"]
        assert "default: ''" in block, lane["workflow"]


def test_the_run_name_keeps_the_workflow_name_when_no_id_is_given():
    """Every event other than a dispatch-with-id shows the workflow name, not an empty one.

    The fallback is written out rather than relying on an empty `run-name` expression
    reverting to GitHub's default, which cannot be verified without a real dispatch.
    """
    for lane in LANES:
        assert "|| github.workflow }}" in workflow_text(lane), lane["workflow"]
#: Lanes whose workflow does not run on the landing push and is therefore always
#: dispatched by the tool. Adding one here is a deliberate statement that the landing
#: push produces no run for it.
DISPATCH_ONLY_WORKFLOWS = {"ac11-security-scan.yml"}


def push_triggered_workflows(ref: str) -> set[str]:
    """Every workflow file whose `push` trigger lists `ref`.

    `yaml.BaseLoader` is deliberate: under YAML 1.1 a plain loader turns the key `on`
    into the boolean `True`, so the trigger block would be unreachable by name.
    """
    import yaml

    found = set()
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        triggers = document.get("on") if isinstance(document, dict) else None
        push = triggers.get("push") if isinstance(triggers, dict) else None
        branches = push.get("branches") if isinstance(push, dict) else None
        if isinstance(branches, list) and ref in branches:
            found.add(path.name)
    return found


def test_every_push_triggered_workflow_has_a_lane():
    """A workflow added to the repository must not quietly leave the landing proof.

    The landing push creates one run per workflow that triggers on `DEFAULT_REF`. If the
    lane list misses one, the evidence reports every lane green while that run was never
    read -- a red lane lands silently. The tool itself cannot notice: it only walks
    `LANES` and never looks at `.github/workflows`. So the comparison lives here.

    This is the test that was missing when `portal-login-harness.yml` arrived with
    `#259`: nothing in 77 cases could fail, because every one of them iterated `LANES`.
    """
    expected = push_triggered_workflows(DEFAULT_REF)
    covered = {lane["workflow"] for lane in LANES} - DISPATCH_ONLY_WORKFLOWS
    missing = expected - covered
    assert not missing, (
        f"these workflows run on the landing push to {DEFAULT_REF} but have no lane: "
        f"{sorted(missing)}"
    )
    stale = covered - expected
    assert not stale, (
        f"these lanes name a workflow that no longer runs on the landing push: "
        f"{sorted(stale)} -- either restore the push trigger or move the workflow into "
        f"DISPATCH_ONLY_WORKFLOWS"
    )


def test_the_dispatch_only_lane_really_does_not_run_on_the_landing_push():
    """The exception list is not a place to park a workflow that does trigger on push."""
    on_push = push_triggered_workflows(DEFAULT_REF)
    for workflow in DISPATCH_ONLY_WORKFLOWS:
        assert workflow not in on_push, (
            f"{workflow} triggers on the landing push, so it does not belong in "
            f"DISPATCH_ONLY_WORKFLOWS"
        )
        assert workflow in {lane["workflow"] for lane in LANES}, workflow


def test_the_portal_login_harness_lane_names_the_job_the_workflow_defines():
    """The lane added for `#259`'s workflow, pinned to that file rather than to prose."""
    import yaml

    document = yaml.load(
        (WORKFLOW_DIR / "portal-login-harness.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    lane = next(item for item in LANES if item["workflow"] == "portal-login-harness.yml")
    assert set(lane["jobs"]) <= set(document["jobs"]), lane["jobs"]
    assert lane["jobs"] == {"portal-login-harness": 1}
    assert document["on"]["push"]["branches"] == [
        "main",
        "integration/all-agents-unified",
        "agent/**",
    ]
