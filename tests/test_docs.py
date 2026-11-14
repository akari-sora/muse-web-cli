import argparse
import re
import tomllib
from pathlib import Path

import pytest

from muse_web_cli import __version__
from muse_web_cli.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills" / "muse-web-cli" / "SKILL.md").read_text(encoding="utf-8")
URLS = (
    "https://gitlab.com/aa22396584/trinity-cli",
    "https://gitlab.com/aa22396584/chatgpt-dot-cli",
    "https://gitlab.com/aa22396584/grok-bot-cli",
    "https://gitlab.com/aa22396584/muse-web-cli",
)
# English: README.md + docs/reference.md. 中文：README.zh-TW.md + docs/reference.zh-TW.md.
LANGUAGES = {
    "en": ("README.md", "docs/reference.md"),
    "zh-TW": ("README.zh-TW.md", "docs/reference.zh-TW.md"),
}


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.fixture(params=sorted(LANGUAGES))
def docs(request):
    readme, reference = LANGUAGES[request.param]
    return _read(readme), _read(reference)


def test_every_command_has_help_and_is_documented(docs):
    readme, reference = docs
    parser = build_parser()
    help_text = parser.format_help()
    assert "examples:" in help_text
    for flag in ("--json", "--port", "--backend", "--autostart", "--chrome"):
        assert flag in help_text
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    assert subparsers.choices
    for name, sub in subparsers.choices.items():
        assert name in readme
        assert name in reference
        assert name in SKILL
        text = sub.format_help()
        assert name in text
        assert len(text.strip()) > 40
        for action in sub._actions:
            if action.help in {None, argparse.SUPPRESS}:
                continue
            assert str(action.help).strip()


def test_readme_links_the_family_and_the_credential_schema(docs):
    readme, reference = docs
    for url in URLS:
        assert url in readme
    for key in ("base_url", "timeout_s", "bearer", "header_name", "endpoints"):
        assert key in reference
        assert key in SKILL or key in ("header_name",)
    assert "trinity-cli" in SKILL
    assert "xvfb-run" in readme
    assert "PowerShell" in readme


def test_version_changelog_and_install_pins_agree(docs):
    readme, reference = docs
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert __version__ == version
    # An [Unreleased] section may sit above the released versions; the release process renames it.
    newest = re.search(r"^## \[(?!Unreleased\])([^\]]+)\]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert newest and newest.group(1) == version
    assert set(re.findall(r"muse-web-cli\.git@v([^\"\s]+)", readme)) == {version}
    assert set(re.findall(r"muse-web-cli\.git@v([^\"\s]+)", reference)) <= {version}
    assert f"muse-web-cli {version}" in readme
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert f'name = "muse-web-cli"\nversion = "{version}"' in lock


def test_docs_say_where_the_token_goes(docs):
    readme, reference = docs
    for text in (readme, SKILL, build_parser().format_help()):
        assert "muse-credential" in text
        assert "mode 600" in text
    for stale in ("does not export the login", "也不會把登入狀態另存一份", "never extracts cookies or tokens"):
        assert stale not in readme
        assert stale not in reference
