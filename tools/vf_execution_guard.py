"""Execution-only pytest guard for the VF runner, including config/env options."""
import pytest


def pytest_configure(config):
    if config.option.collectonly:
        raise pytest.UsageError('VF execution evidence requires test bodies; collect-only is not allowed')
