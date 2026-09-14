# Approval browser integration

This test mounts the production ApprovalCenter and API helpers in a test-only Vite entry.
It runs the configured production server factory over loopback HTTP, an isolated PostgreSQL
cluster upgraded to migration head, and a real headless browser. It uses synthetic JWTs;
it does not verify the App login flow, a real identity provider, or a remote Node.

Install web dependencies with npm ci and Python requirements-browser.txt. On Windows,
installed Edge is used. On other systems install Chromium with python -m playwright install chromium.
Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL administrator connection and INV_BROWSER_TEST=1,
then run python -m pytest -q tests/integration/test_approval_browser.py.
Never point this test at an operational database: the integration fixture creates database roles.
Without explicit opt-in the browser cases skip; a skipped test is not browser validation.
No browser artifact is captured except an optional synthetic screenshot in .work. Tokens stay in memory.

From the repository root, python tools/run_approval_browser_test.py creates a dedicated Docker PostgreSQL cluster, enables these tests, and removes only that owned container afterward. Docker postgres:16 must be available.

The same runner now also tests the full /studio login/project/approval/logout entry with a local synthetic OAuth server. See ../../STUDIO_AUTH.md for that separate scope; operational IdP acceptance remains pending.
