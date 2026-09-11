"""Container-only test entry; ephemeral DB credentials never enter argv or logs."""
from pathlib import Path
import json
import os
import subprocess
import sys


def main():
    config = json.loads(Path('/run/test/config.json').read_text())
    environment = dict(os.environ, INV_TEST_ADMIN_DSN=config['adminDSN'],
                       INV_RUN_NODE_TESTS='1', INV_NODE_IMAGE=config['nodeImage'],
                       INV_PYTHON_NODE_IMAGE=config['nodeImage'],
                       INV_TEST_EVIDENCE_DIR='/evidence',
                       INV_NODE_BINARY='/app/binaries/inv-node',
                       INV_DISCOVER_BINARY='/app/binaries/inv-discover')
    tests = config['tests']
    if not tests or any(not name.startswith(('tests/integration/test_', 'tests/test_')) or not name.endswith('.py') or '..' in name for name in tests):
        raise ValueError('Explicit integration test files required')
    # Capture to a private artifact. Test assertion traces can contain DB fixtures.
    # Public evidence is separately extracted from the JUnit status attributes.
    with Path('/evidence/pytest.log').open('wb') as log:
        result = subprocess.run([sys.executable, '-m', 'pytest', '--maxfail=10', '-q',
                                 '--junitxml=/evidence/tests.xml', '-o', 'faulthandler_timeout=45',
                                 '--basetemp=/tmp/kernel-tests', *tests], env=environment,
                                stdout=log, stderr=subprocess.STDOUT, timeout=900)
    print(json.dumps({'exitCode': result.returncode, 'scope': 'isolated-kernel-integration'}), flush=True)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
