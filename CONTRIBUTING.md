# Contributing to muse-web-cli

中文：歡迎用中文開 issue 或 merge request。

Thanks for helping. Bug reports, fixes, and docs changes are all welcome.

## Development setup

Python 3.11+ and [uv](https://docs.astral.sh/uv/). The tests do not start Chrome.

```bash
git clone https://gitlab.com/aa22396584/muse-web-cli.git
cd muse-web-cli
uv venv
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 uv pip install -e . "pytest>=8"
.venv/bin/python -m pytest -q
```

Windows (PowerShell): set `$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1"` before the install, then `.venv\Scripts\python.exe -m pytest -q`.

## Ground rules

- Tests use fake pages and fake HTTP. They never open muse.ai and never read a real profile or credential file.
- Do not add code or docs that extract cookies or tokens from a browser, replay requests outside the browser, or click settings, connectors, approvals, or attachments. The `api` backend only reads a credential file the user supplies.
- Never commit tokens, cookies, credential files, account, chat, or bot ids, message text, emails, IP addresses, host names, or absolute local paths. Use fake values in tests and docs.
- Keep `README.md` and `README.zh-TW.md` in sync, and `docs/reference.md` and `docs/reference.zh-TW.md` in sync.
- A bug fix comes with a test that fails without it.
- One topic per merge request. Describe how you tested it.

## CI

GitLab CI runs the tests on Linux for every push and on Windows for merge requests (manual), tags, and `main`. A fork uses GitLab.com shared runners by default. Set the `LINUX_RUNNER_TAG` and `WINDOWS_RUNNER_TAG` CI/CD variables to use other runners. There is no macOS CI; maintainers test macOS locally.

## Release process (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in `src/muse_web_cli/__init__.py`, then run `uv lock`.
2. Update the install pins (`@vX.Y.Z`) and the `muse-web-cli X.Y.Z` version line in `README.md` and `README.zh-TW.md`.
3. Add a `## [X.Y.Z] - YYYY-MM-DD` heading at the top of `CHANGELOG.md`. `tests/test_docs.py` and the tag pipeline both read it.
4. Merge to `main` and wait for a green pipeline.
5. Tag `vX.Y.Z` on `main` and push the tag. The tag pipeline checks the version and creates the GitLab Release.

Never move or delete a published tag. Fix forward with a new version.
