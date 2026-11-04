import pytest

from tools.check_docs import dependency_status_errors


def task(task_id, status, depends_on=None):
    return {
        'task_id': task_id,
        'status': status,
        'depends_on': depends_on or [],
    }


@pytest.mark.parametrize('status', ['ready', 'in_progress', 'review', 'done'])
def test_active_task_rejects_unmet_dependency(status):
    tasks = [task('S01-BE', 'blocked'), task('S02-BE', status, ['S01-BE'])]

    assert dependency_status_errors(tasks) == [
        'Active task has unmet dependencies: S02-BE -> S01-BE'
    ]


@pytest.mark.parametrize('status', ['planned', 'blocked'])
def test_inactive_task_allows_unmet_dependency(status):
    tasks = [task('S01-BE', 'blocked'), task('S02-BE', status, ['S01-BE'])]

    assert dependency_status_errors(tasks) == []


def test_active_task_allows_completed_dependency():
    tasks = [task('S01-BE', 'done'), task('S02-BE', 'review', ['S01-BE'])]

    assert dependency_status_errors(tasks) == []
